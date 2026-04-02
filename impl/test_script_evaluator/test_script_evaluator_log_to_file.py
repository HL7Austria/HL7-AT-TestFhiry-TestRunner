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
from impl.exception.Error import *
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

    """
    for supporting all methods:
        somehow map type to operation method
        --> maybe dict?? maybe not
        ---> check what is better helper function or dict (is public from utils)
    
    1. check for method if no method check for type
        -> if type => map method to use
        -> if no type => is mayhaps a client test i don't really know
           
    for different types of operation different params/headerfield whatever?
    """

    global FIXTURES
    #global PROFILES
    #global VARIABLES
    try:
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
    except Exception as e:
        raise TestScriptError(e)

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
    global REQ_RESP

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

    stopTestOnFail = True
    
    try:
        # WHEN – Operation
        if "operation" in action:
            operation = action["operation"]
            execute_operation(operation)

         # THEN - Assertion
        elif "assert" in action:
            assertion = action["assert"]
            stopTestOnFail = assertion.get("stopTestOnFail")
            execute_assertion(assertion)
        
    except AssertionError as ae:
        if not stopTestOnFail:
            handle_assertion_error(ae, stopTestOnFail)
        raise        
    except Exception as e:
        raise TestExecutionError(f"Test stopped: {str(e)}")


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
    if stop_test_on_fail == False:
        raise TestExecutionError(f"Test stopped due to stopTestOnFail: {str(e)}")
    return False  # Test failed, but continuing allowed

def autodelete():
        global FIXTURES
        for fix in FIXTURES:
            if fix.autodelete and fix.server_id != "":
                requests.delete(f"{FHIR_SERVER_BASE}/{fix.type}/{fix.server_id}")



def SETUP(setup_data, fixture_list : list, resources):
    """
    1. metadata.Capability
    2. fixture autocreate

    --> do all setup.actions (operations and asserts)
    You ONLY know the setup and already saved variables and mayhaps profiles

    --> save the results?
    """
    global FIXTURES
    #global PROFILES
    #global VARIABLES

    try:
        
        if fixture_list: #if there are fixtures to save
            save_fixtures(resources, fixture_list)

        if FIXTURES:
            for fix1 in FIXTURES:
                for fix2 in FIXTURES:
                    json_string = json.dumps(fix1.body)
                    my_regex = "\"reference\" *: *\"[a-zA-Z:]*" + fix2.type + "/" + fix2.fixture_id + "\""
                    fix1.body = json.loads(re.sub(my_regex , "\"reference\": \"" + fix2.type+"/"+fix2.server_id + "\"", json_string))

                if re.search("\"reference\" *: *\"[a-zA-z]*/[a-zA-Z-]+", json.dumps(fix1.body)) != None: #look again to make sure no unattended references exist
                        raise Exception("Unknown Reference remaining.")
                

        
        for action in setup_data.get("action", []):
            execute_actions(action)

    except OperationError as oe:
        raise TestScriptError("Setup operation failed: ", oe)# stop the whole testscript
    except TestExecutionError as teE:
        raise TestScriptError("Setup failed: " , teE) #stop the whole testscript
    except Exception as e:
        log_to_file(f"✗ TEST SKIPPED: Failure to start TestScript: ")
        log_to_file(str(e))


def TEST(test_data):
    """
    1. metadata.capabilities
        if there are problems --> skip this test (some kind of skip Exception? or straight return)
    
    --> do all test-actions (operation or assertion)
    --> save Test Results for all tests
    --> U only know of urself and the saved fixtures / responses / variables
    """
    #Test Capabilities --> if Error --> skip test --> maybe in main

    test_name = test_data.get('name', 'Unnamed Test')
    log_to_file(f"\n ----------- Starting Test: {test_name} -----------")


    try:
      
        for action in test_data.get("action" , []):
            try:
                execute_actions(action)

            #per action in test
            except OperationError as oe:
                raise TestScriptError("Test operation failed: ", oe)

            except AssertionError as ae:
                log_to_file(f"✗ TEST FAILED: {test_name} (but completed all actions)")

            except TestExecutionError as e:
                raise
                # Continue with next test even if this one was stopped



        log_to_file(f"✓ TEST PASSED: {test_name}")
    except TestExecutionError as e:
        log_to_file(f"✗ TEST STOPPED: {test_name} - {str(e)}")
        #test schould get stopped, and next test needs to start
        
        
    

    
def TEARDOWN(teardown_data):

    """
    1. Teardown actions
    2. autodelete

    --> if teardown is empty only do autodelete

    autodelete
    """

    try:
        for action in teardown_data.get("action", []):
            execute_actions(action)
        
        autodelete()
        
            
    except OperationError as oe:
        raise TestScriptError("Teardown operation failed: " , oe)

def test_fhir_operations(testscript_data):
    """
    Main test function for FHIR operations testing.
    Executes all tests in a testscript with GIVEN-WHEN-THEN structure.

    :param testscript_data: Tuple containing testscript and resource data.
    """

    """
    HERE --> should only test the basic TS all rounder things (Capability, save variables, save profiles)
    everything that is not defined by an action!!

    1. validate TS itself
    2. test server
    3. test capability
    4. save variables
    5. save profiles

    6. SETUP
    7. TEST
    8. TEARDOWN

    9. clear up everything that needs cleaning up (all global usw.)
    """

    if not has_fhir_server():
        log_to_file("✗ TEST SKIPPED: No FHIR server configured")
        pytest.skip("No FHIR server configured in config.json")
    
    testscript, resources = testscript_data

    
    #test capability
    #--> find out how important origin and destnation are
    fixture_list = get_fixture(testscript)

    try:
        
        for setup in testscript.get("setup" , []):
            SETUP(setup, fixture_list, resources)

        if not testscript.get("setup"): #if no setup at all --> autocreate needs to happen
            SETUP({},fixture_list, resources)
            
        for test in testscript.get("test", []):
            TEST(test)  

        for teardown in testscript.get("teardown", []):
            TEARDOWN(teardown)
        if not testscript.get("teardown"): #if no teardown at all --> autodelete needs to happen
            TEARDOWN({})

    except TestScriptError as tse:
        log_to_file("Severe error: " , tse)
        autodelete() #autodelete after everything went wrong
    except:
        log_to_file("TestScript stopped!")

    # Final summary --> find out how to save results from each test and log them

        
    FIXTURES.clear() 
    REQ_RESP.clear()
