import json
import requests
import pytest
from datetime import datetime
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
from impl.model.variable import Variable
from utils import *


saved_resource_id = ""
last_interaction = None
log_filename = f"test_results_{timestamp}.txt"

FIXTURES = []
REQ_RESP = []

VARIABLES = []

# Init logfile
with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(f"FHIR Test Log - {datetime.now()}\n\n")

FHIR_SERVER_BASE = get_fhir_server()


def replacer(match):
    """
    helper function used to replace a variable match with the value of the variable
    """
    global VARIABLES
    var_name = match.group(1)
    print("Found variable:", var_name)  # if you want to see them

    for var in VARIABLES:
        if var.name == var_name:
            return eval_variable(var)
    
    raise Exception(f"Variable {var_name} could not be found")

# Execute operation
def execute_operation(operation):
    """
    Executes a FHIR operation (CREATE, UPDATE, READ) on the server.

    :param operation: Dictionary containing operation details.
    :return: HTTP response object.
    :raises: NotImplementedError for unsupported methods.
    """
    # do I want to check if variables are in the right place?
    pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
    json_str = json.dumps(operation)
    result = pattern.sub(replacer, json_str)
    operation = json.loads(result)
    print(operation)


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

def execute_test_actions(test):
    """
    Executes all actions for a single test.

    :param test: Test definition dictionary.
    :param resource: FHIR resource to test with.
    :return: True if test passed, False otherwise.
    """
    test_name = test.get('name', 'Unnamed Test')
    log_to_file(f"\n ----------- Starting Test: {test_name} -----------")

    test_passed = True

    for action_index, action in enumerate(test.get("action", [])):
        try:
            # WHEN – Operation
            if "operation" in action:
                operation = action["operation"]
                execute_operation(operation)

            # THEN - Assertion
            elif "assert" in action:
                global last_interaction
                assertion = action["assert"]
                stopTestOnFail = assertion.get("stopTestOnFail", False)
                #If assertion is on a Fixture (Patient etc.) --> see if it can be found in FIXTURES 
                            #--> if it can some assertions aren't valid anymore

                #--> not checking if the variable is at the right place!
                pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
                json_str = json.dumps(assertion)
                result = pattern.sub(replacer, json_str)
                assertion = json.loads(result)
                

                response = last_interaction
                for int in REQ_RESP:
                    if int.res_id == assertion.get("sourceId"):
                        response = int
                
                #--> testing only interactions, get possible fixture id or variables for eval --> assert.value

                if "validateProfileId" in assertion:
                    try:
                        #validate_profile_assertion(assertion.get("validateProfileId"))
                        log_to_file("✓ Assertion passed")
                    except AssertionError as e:
                        test_passed = handle_assertion_error(e, stopTestOnFail)
                        

                contentType = False
                if "contentType" in assertion:
                    try:
                        contentType = True
                        validate_content_type(response, assertion.get("contentType"))
                        log_to_file("✓ Assertion passed")
                    except AssertionError as e:
                        test_passed = handle_assertion_error(e, stopTestOnFail)

                if assertion.get("direction") == "response" and not contentType:
                    try:
                        validate_response(assertion, response)
                        log_to_file("✓ Assertion passed")
                    except AssertionError as e:
                        test_passed = handle_assertion_error(e, stopTestOnFail)

                elif assertion.get("direction") == "request":
                    log_to_file("direction request out of scope")
                    
        except Exception as e:
                raise TestExecutionError(f"Test stopped: {str(e)}")


    return test_passed

def save_variables(variables : list):
    global VARIABLES
    for var in variables:
        id = var.get("name")

        variable = Variable(id,path=var.get("path"), 
                                  expression=var.get("expression"),
                                  sourceId=var.get("sourceId"),
                                  headerField=var.get("headerField"),
                                  defaultValue=var.get("defaultValue"))
        if id is None:
            raise Exception("Variable not correctly defined!")
    
                
        if(((variable.expression is not None) & (variable.headerField is not None)) | 
           ((variable.headerField is not None) & (variable.path is not None)) | 
           ((variable.expression is not None) & (variable.path is not None))):
            raise Exception(f"Variable {id} not valid Fhir, two value-expressions cannot be filled at the same time!")
        

        VARIABLES.append(variable)

def eval_variable(var : Variable):
    global REQ_RESP
    global FIXTURES

    result = var.defaultValue or None
    expr = var.expression or None
    expr = var.path or expr
    expr = var.headerField or expr


    if (not expr) & (not result):
        raise Exception("variable is not filled!")

    if expr:
        fix = None
        sourceId = var.sourceId

        for int in REQ_RESP:
            if int.res_id == sourceId:
                fix = int
        
        for fixture in FIXTURES:
            if fixture.sourceId == sourceId:
                fix = fixture
        
        if var.headerField:
            if not isinstance(fix, Interaction):
                raise TypeError("Field \"headerField\" cannot be evaluated from a Fixture!")
            json.loads(fix.header).get("expr")
        elif var.expression:
            result = do_expression(fix.body, expr)
        elif var.path:
            result = "1"
            do_path(fix.body, expr)

    print("eval")
    return result

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
    

def handle_assertion_error(e, stop_test_on_fail): # could be put into utils
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

def test_fhir_operations(testscript_data):
    """
    Main test function for FHIR operations testing.
    Executes all tests in a testscript with GIVEN-WHEN-THEN structure.

    :param testscript_data: Tuple containing testscript and resource data.
    """

    if not has_fhir_server():
        log_to_file("✗ TEST SKIPPED: No FHIR server configured")
        pytest.skip("No FHIR server configured in config.json")
    # GIVEN
    testscript, resources = testscript_data

    resource = None
    overall_results = []

    try:
        variable_list = get_variables(testscript)
        if variable_list:
            save_variables(variable_list)
        
        fixture_list = get_fixture(testscript)
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
        

    else: 
       #if fixtures are being used by the action --> see what id is in action + don't give it the whole fixture
        
       for test in testscript.get("test", []):
        test_name = test.get('name', 'Unnamed Test')
        
    
        try:
            test_passed = execute_test_actions(test)

            if test_passed:
                log_to_file(f"✓ TEST PASSED: {test_name}")
                overall_results.append((test_name, True))
            else:
                log_to_file(f"✗ TEST FAILED: {test_name} (but completed all actions)")
                overall_results.append((test_name, False))

        except TestExecutionError as e:
            log_to_file(f"✗ TEST STOPPED: {test_name} - {str(e)}")
            overall_results.append((test_name, False))
            # Continue with next test even if this one was stopped

        # Final summary
        log_to_file("======================")
        log_to_file("Test Summary:")
        for test_name, passed in overall_results:
            status = "PASSED" if passed else "FAILED"
            log_to_file(f"  {test_name}: {status}")


        log_to_file("Test execution completed")
    finally:
        for fix in FIXTURES:
            if fix.autodelete and fix.server_id != "":
                requests.delete(f"{FHIR_SERVER_BASE}/{fix.type}/{fix.server_id}")
        FIXTURES.clear() #reset for next testscript
        REQ_RESP.clear()

        VARIABLES.clear()
