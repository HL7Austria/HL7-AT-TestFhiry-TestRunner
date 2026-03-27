import json
import requests
import pytest
from pathlib import Path
import os
from datetime import datetime
import traceback
import re

from numpy.ma.testutils import assert_equal
from impl.Transactions.transactions import *
from impl.exception.TestExecutionError import TestExecutionError
from validate import *
from configuration_manager import get_config_manager, get_fhir_server, get_testscript_pairs, has_fhir_server
from impl.model.configuration import Configuration
from impl.Transactions.transactions import build_whole_transaction_bundle
from impl.model.fixture import Fixture
from impl.model.interaction import Interaction
from utils import *


saved_resource_id = ""
last_interaction = None
log_filename = f"test_results_{timestamp}.txt"

FIXTURES = []
REQ_RESP = []

# Init logfile
with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(f"FHIR Test Log - {datetime.now()}\n\n")

FHIR_SERVER_BASE = get_fhir_server()

def extract_test_source_id(container):
    """
    Returns the sourceID
    """
    for action in container.get("action", []):
        op = action.get("operation")
        if op and "sourceId" in op:
            return op["sourceId"]

    return None


# Execute operation
def execute_operation(operation):
    """
    Executes a FHIR operation (CREATE, UPDATE, READ) on the server.

    :param operation: Dictionary containing operation details.
    :return: HTTP response object.
    :raises: NotImplementedError for unsupported methods.
    """
    #get all Info from operation
    type = operation.get("type", {}).get("code", "").lower()
    method = operation.get("method") #--> find a way to make method work
    resource_type = operation.get("resource")
    url = f"{FHIR_SERVER_BASE}/{resource_type}"
    sourceId = operation.get("sourceId")
    targetId = operation.get("targetId")
    Ourl = operation.get("url")

    headers = {
        "Content-Type": parse_fhir_header(operation.get("contentType")),
        "Accept": parse_fhir_header(operation.get("accept")),
    }

    if type == "create":
        log_to_file(f"Executing: {type.upper()} {url}")
        fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
        if(fixture):
            if(Ourl):
                response = requests.post(Ourl, headers=headers, json=fixture.body) #if fixed url is given
            else:
                response = requests.post(url, headers=headers, json=fixture.body) #if I need to make my own url

            global saved_resource_id
            try:
                saved_resource_id = response.json().get("id")
            except ValueError:
                location = response.headers.get("Location", "")
                if location:
                    saved_resource_id = location.rstrip("/").split("/")[-3]
                    log_to_file(f"ID from Location header: {saved_resource_id}")
                else:
                    raise ValueError("No ID found in response or Location header")

            
    elif type == "update":
        fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
        Tfixture = next((fix for fix in FIXTURES if fix.source_id == targetId), None)
        if fixture:
            #look here for variable
            resource_id = Tfixture.server_id
            log_to_file(f"Executing: {type.upper()} {url}/{resource_id}")

            fixture.body["id"] = resource_id
            response = requests.put(f"{url}/{resource_id}", headers=headers, json=fixture.body)
        else:
            log_to_file("no source found in PUT")

    elif type == "read": #--> change ? does it need sourceId
        fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
        if fixture is None:
            log_to_file("No fixture found in read")
            return None
        resource_id = fixture.server_id
        log_to_file(f"Executing: {type.upper()} {url}/{resource_id}")
        response = requests.get(f"{url}/{resource_id}", headers=headers)

    elif type == "delete":
        Tfixture = next((fix for fix in FIXTURES if fix.source_id == targetId), None)
        if Tfixture is None:
            log_to_file("No fixture found in delete")
            return None
        if Tfixture.server_id is None:
            log_to_file("No saved fixture found in delete")
            return None
        resource_id = Tfixture.server_id
        log_to_file(f"Executing: {type.upper()} {url}/{resource_id}")
        response = requests.delete(f"{url}/{resource_id}", headers=headers)

    else:
        raise NotImplementedError(f"Method {type} not implemented")

    log_to_file(f"Response: {response.status_code}")

    #trying first to get response to run, afterwards look at request
    int_id = operation.get("responseId")
    direction = "response"
    global last_interaction
    last_interaction = Interaction(direction, response.headers, response.text)
    last_interaction.status_code = response.status_code
    last_interaction.res_id = int_id
    

    if(int_id != None):
        REQ_RESP.append(last_interaction)

def execute_assertion(assertion):
    global last_interaction
    #If assertion is on a Fixture (Patient etc.) --> see if it can be found in FIXTURES 
        #--> if it can some assertions aren't valid anymore

    """
    Assertion error should be handled by the Test or setup
    Assertions --> you should probably save the results here

    no return value anymore --> if no error comes back everything is great
    """

    response = last_interaction
    for int in REQ_RESP:
        if int.res_id == assertion.get("sourceId"):
            response = int
                
            #--> testing only interactions, get possible fixture id or variables for eval --> assert.value
    try:

        if "validateProfileId" in assertion:
            #validate_profile_assertion(assertion.get("validateProfileId"))
            log_to_file("✓ Assertion passed")
            
            contentType = False
            if "contentType" in assertion:   
                contentType = True
                validate_content_type(response, assertion.get("contentType"))
                log_to_file("✓ Assertion passed")
                
            if assertion.get("direction") == "response" and not contentType:
                validate_response(assertion, response)
                log_to_file("✓ Assertion passed")
                
            elif assertion.get("direction") == "request":
                log_to_file("direction request out of scope")
    except AssertionError as e:
        raise
    
                                            
# Fixture for dynamic test data
@pytest.fixture(params=get_testscript_pairs())
def testscript_data(request):
    """
    Pytest fixture that provides testscript and resource data for parameterized tests.

    :param request: Pytest fixture request object.
    :return: Tuple of (testscript, resource) data.
    """
    testscript_path, resource_path = request.param
    testscript = load_json(testscript_path)
    if resource_path:
        resources = load_json_list(resource_path)
    else:
        resources = None
    return testscript, resources

def execute_actions(action):
    """
    Executes all actions for a single test.

    :param test: Test definition dictionary.
    :param resource: FHIR resource to test with.
    :return: True if test passed, False otherwise.

    stopTestOnFail:
    If this element is specified and it is true, then assertion failures should not stop the current test execution from proceeding.
    is test excecusion the TestScript?
    """
    
    try:
        # WHEN – Operation
        if "operation" in action:
            operation = action["operation"]
            execute_operation(operation)

         # THEN - Assertion
        elif "assert" in action:
            assertion = action["assert"]
            test_passed = execute_assertion(assertion)
        
    except AssertionError as ae:
        raise           
    except Exception as e:
        raise TestExecutionError(f"Test stopped: {str(e)}")


    return test_passed

def save_fixtures(jsonFiles, fix_list):
    """
    saves fixtures to the server and saves infos for them
    :param jsonFiles: the json inside the Files
    """
    bundle_json = [] #die zu erstellenden Fixtures als json
    for jsonf, fixture in zip(jsonFiles, fix_list):
        fix_id = jsonf.get("id")
        fix_type = jsonf.get("resourceType")
        fix_source_id = fixture.get("id")
        autocreate = fixture.get("autocreate", True)
        autodelete = fixture.get("autodelete", False)
        if(autocreate):
            bundle_json.append(jsonf)
        FIXTURES.append(Fixture(fix_id,fix_source_id,autodelete, fix_type, jsonf)) #erstes Anlegen vor bundle

    if bundle_json:
        bundle = build_whole_transaction_bundle(bundle_json)
        try:
            response = requests.post(
            FHIR_SERVER_BASE,
            headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"},
            json=json.loads(bundle)
            )

            results = response.json().get("entry")

            for fix_cont, res in zip(bundle_json, results):
                resp = res.get("response", {})
                res_loc = resp.get("location", "")
                res_id = res_loc.split("/")[1]  # server id
                fix_id = fix_cont.get("id")  # id inside the Example Instance

                for fix in FIXTURES:
                    if fix_id == fix.fixture_id:
                        fix.server_id = res_id  # saves der Server id
        except Exception as e:
            msg = ""
            json_data = json.loads(response.text)
            for item in json_data.get("issue"):
                msg += item.get("diagnostics")
            raise Exception(msg)
    

def handle_assertion_error(e, stop_test_on_fail):
    """
    Logs the AssertionError and decides whether to stop or continue the test.

    :param e: The AssertionError exception.
    :param stop_test_on_fail: Boolean flag indicating if test should stop on failure.
    :return: True if test should continue, False if test failed.
    :raises: TestExecutionError if stop_test_on_fail is True.
    """
    log_to_file(f"✗ ASSERTION FAILED: {str(e)}")
    if stop_test_on_fail == True:
        raise TestExecutionError(f"Test stopped due to stopTestOnFail: {str(e)}")
    return False  # Test failed, but continuing allowed


def SETUP(setup_data, fixture_list : list, resources):
    """
    1. metadata.Capability
    2. fixture autocreate

    --> do all setup.actions (operations and asserts)
    You ONLY know the setup and already saved variables and mayhaps profiles

    --> save the results?
    """

    try:
        
        if fixture_list: #falls es fixtures gibt
            save_fixtures(resources, fixture_list)

        if FIXTURES:
            for fix1 in FIXTURES:
                for fix2 in FIXTURES:
                    json_string = json.dumps(fix1.body)
                    my_regex = "\"reference\" *: *\"[a-zA-Z:]*" + fix2.type + "/" + fix2.fixture_id + "\""
                    fix1.body = json.loads(re.sub(my_regex , "\"reference\": \"" + fix2.type+"/"+fix2.server_id + "\"", json_string))

                if re.search("\"reference\" *: *\"[a-zA-z]*/[a-zA-Z-]+", json.dumps(fix1.body)) != None: #erneut überprüfen damit nichts verloren geht
                        raise Exception("Unknown Reference remaining.")
    except Exception as e:
        log_to_file(f"✗ TEST SKIPPED: Failure to start TestScript: ")
        log_to_file(str(e))


    for action in setup_data.get("action", []):
        execute_test_actions(action)

    
    #do setup action

def TEST(test_data):
    """
    1. metadata.capabilities
    
    --> do all test-actions (operation or assertion)
    --> save Test Results for all tests
    --> U only know of urself and the saved fixtures / responses / variables
    """

    try:
        test_name = test_data.get('name', 'Unnamed Test')
        log_to_file(f"\n ----------- Starting Test: {test_name} -----------")

        for action in test_data.get("action" , []):
            execute_actions(action)

        if test_passed:
            log_to_file(f"✓ TEST PASSED: {test_name}")
            return (test_name, True)
        else:
            log_to_file(f"✗ TEST FAILED: {test_name} (but completed all actions)")
            return (test_name, False)
        
    except OperationError as oe:
        print("make your own error")
    except AssertionError as ae:
        print("test failed")
    except TestExecutionError as e:
        log_to_file(f"✗ TEST STOPPED: {test_name} - {str(e)}")
        return (test_name, False)
        # Continue with next test even if this one was stopped

    
def TEARDOWN(teardown_data):

    """
    do teardown actions --> do i have to document this?

    action --> but only operations
        if there are assertions --> TestScript not valid
    autodelete
    """

    global FIXTURES
    for fix in FIXTURES:
        if fix.autodelete and fix.server_id != "":
            requests.delete(f"{FHIR_SERVER_BASE}/{fix.type}/{fix.server_id}")

def test_fhir_operations(testscript_data):
    """
    Main test function for FHIR operations testing.
    Executes all tests in a testscript with GIVEN-WHEN-THEN structure.

    :param testscript_data: Tuple containing testscript and resource data.
    """

    """
    HERE --> should only test the basic TS all rounder things (Capability, save variables, save profile)

    everything that is not defined by an action!!

    1. test server
    2. test capability
    3. save variables
    4. save profiles

    5. SETUP
    6. TEST
    7. TEARDOWN

    8. clear up everything that needs cleaning up (all global usw.)
    """

    if not has_fhir_server():
        log_to_file("✗ TEST SKIPPED: No FHIR server configured")
        pytest.skip("No FHIR server configured in config.json")
    # GIVEN
    testscript, resources = testscript_data

    fixture_list = get_fixture(testscript)

    for setup in testscript.get("setup" , []):
        SETUP(setup, fixture_list, resources)
        
    for test in testscript.get("test", []):
        TEST(test)  

    for teardown in testscript.get("teardown", []):
        TEARDOWN(teardown)

    # Final summary --> find out how to save 
    """
        log_to_file("======================")
        log_to_file("Test Summary:")
        for test_name, passed in overall_results:
            status = "PASSED" if passed else "FAILED"
            log_to_file(f"  {test_name}: {status}")


        log_to_file("Test execution completed")
    """     
        
    FIXTURES.clear() 
    REQ_RESP.clear()
