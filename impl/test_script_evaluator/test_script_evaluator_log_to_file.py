import json
import requests
import pytest
from datetime import datetime
import re

from impl.transactions.transactions import *
from typing import Any
from impl.exception.Error import *
from validate import *
from impl.transactions.transactions import *
from configuration_manager import get_fhir_server, get_testscript_pairs, has_fhir_server
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
PROFILES = {} #saving profilesIDs with the references

# Init logfile
with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(f"FHIR Test Log - {datetime.now()}\n\n")

FHIR_SERVER_BASE = get_fhir_server()

def extract_test_source_id(container): #do i even need this anymore?
    """
    Returns the sourceID
    """
    for action in container.get("action", []):
        op = action.get("operation")
        if op and "sourceId" in op:
            return op["sourceId"]

    return None


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


def execute_operation(operation: dict[str, Any]):
    """
    Executes a FHIR operation (CREATE, UPDATE, READ) on the server.

    :param operation: Dictionary containing operation details.
    :raises: NotImplementedError for unsupported methods.
    :raises: TestScriptError for critical Errors while executing.
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
    try:

            # do I want to check if variables are in the right place?
        pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
        json_str = json.dumps(operation)
        result = pattern.sub(replacer, json_str)
        operation = json.loads(result)

        #get all Info from operation
        method = operation.get("method")
        type = operation.get("type", {}).get("code", "").lower()
        url = operation.get("url")
        sourceId = operation.get("sourceId")


        #kümmere dich um die headers
        headers = {
            "Content-Type": parse_fhir_header(operation.get("contentType")),
            "Accept": parse_fhir_header(operation.get("accept")),
        }

        if not method and type:
            method = map_method_type(type) #get method from type if exists
        if not method:
            raise TestScriptError("request method could not be found out!")
        
        if not url:
            url = build_url(operation)
        if type == "create":
            log_to_file(f"Executing: {type.upper()} {url}")
            fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
            if(fixture):
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
            finally:
                log_to_file(f"Accessible at: {url}/{saved_resource_id}")

                
        elif type == "update":
            fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
            if fixture:
                log_to_file(f"Executing: {type.upper()} {url}")

                fixture.body["id"] = url.rstrip("/").split("/")[-1] #if update url is [base]/[type]/[id]
                response = requests.put(f"{url}", headers=headers, json=fixture.body)
            else:
                log_to_file("no source found in PUT")

        elif type == "read":
            log_to_file(f"Executing: {type.upper()} {url}")
            response = requests.get(f"{url}", headers=headers)

        elif type == "delete":
            log_to_file(f"Executing: {type.upper()} {url}")
            response = requests.delete(f"{url}", headers=headers)

        else:
            raise NotImplementedError(f"Method {type} not implemented")
    except Exception as e:
        raise TestScriptError(e)

    log_to_file(f"Response: {response.status_code}")

    #trying first to get response to run, afterwards look at request
    int_id = operation.get("responseId")
    global last_interaction
    last_interaction = Interaction(response.headers, response.text)
    last_interaction.status_code = response.status_code
    last_interaction.reason = response.reason #for later
    last_interaction.res_id = int_id
    

    if(int_id != None):
        REQ_RESP.append(last_interaction)

def build_url(operation :dict [str, Any]) -> str:
    """
    :returns: complete url string 
    :raises: TestScriptError if there is a violation of the Testing How-Tos
    :raises: Exception if XML is needed
    """

    url = FHIR_SERVER_BASE
    params = operation.get("params")
    sourceId = operation.get("sourceId")
    targetId = operation.get("targetId")
    resource = operation.get("resource")
    type = operation.get("type", {}).get("code", "").lower()

    fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
    if not fixture:
        fixture = next((fix for fix in REQ_RESP if fix.res_id == sourceId), None)
    Tfixture = next((fix for fix in FIXTURES if fix.source_id == targetId), None)
    if not Tfixture:
        Tfixture = next((fix for fix in REQ_RESP if fix.res_id == sourceId), None)
    #--> suchen der Fixture wenn leer = None

    if type == "transaction":
        return url
    elif type == "capabilities" and not params:
        return url + "/metadata"

    if params:
        if type == "read" or type == "vread" or type == "update" or type == "delete":
            if not resource:
                raise TestScriptError(f"Resource-Type is needed for Operation {type} {params}")
        elif type == "create" or type =="transaction":
            raise TestScriptError("Create and transaction should not have params!")
        
        if resource:
            url += "/" + resource
        return url + params
    else:
        if not type:
            raise TestScriptError("Could not create url for Operation!")
        
        if sourceId:
            if not fixture:
                raise TestScriptError(f"Fixture {sourceId} could not be found")
            url += "/" + fixture.body.get("resourceType")
        
        if targetId:
            if type == "search":
                raise TestScriptError("targetId should not be used with search.")

            id = ""
            vid = ""
            url_type = ""
            if isinstance(Tfixture, Interaction):
                if "Location" in Tfixture.header:
                    location = Tfixture.header.get("Location")
                    if "_history" in location:
                        id = location.rstrip("/").split("/")[-3]
                        vid = location.rstrip("/").split("/")[-1]
                    else:
                        id = location.rstrip("/").split("/")[-1]
                else:
                    if isinstance(Tfixture.body, dict):
                        id = Tfixture.body.get("id")
                        vid = Tfixture.body.get("meta").get("versionId")
                    elif string_type(Tfixture.body) == "json":
                        body = json.loads(Tfixture.body)
                        id = body.get("id")
                        vid = body.get("meta").get("versionId")
                    else:
                        raise Exception("XML is not supported as of now")
            elif isinstance(Tfixture, Fixture):
                id = Tfixture.server_id
            else:
                raise TestScriptError(f"Fixture {targetId} not found!")
            
            if isinstance(Tfixture.body, dict):
                url_type = Tfixture.body.get("resourceType")
            elif string_type(Tfixture.body) == "json":
                body = json.loads(Tfixture.body)
                url_type = body.get("resourceType")
            else:
                raise Exception("XML is not supported as of now")
            
            if type == "vread":
                if vid == "":
                    raise OperationError("No versonId found for vread Operation.")
                return url +  "/" + url_type +  "/" + id + "_history" +  "/" + vid
            elif type == "history":
                return url +  "/" + url_type +  "/" + id + "_history"
            else:
                if type == "create":
                    raise TestScriptError("Create should not have a targetId")
                elif type == "update" and sourceId:
                    return url +  "/" + id
                else:
                    return url +  "/" + url_type +  "/" + id


def execute_assertion(assertion : dict[str,Any]) -> None:
    global last_interaction

    """
    Assertion error should be handled by the Test or setup
    Assertions --> you should probably save the results here

    no return value anymore --> if no error comes back everything is great
    """
    global REQ_RESP

    #--> not checking if the variable is at the right place!
    pattern = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
    json_str = json.dumps(assertion)
    result = pattern.sub(replacer, json_str)
    assertion = json.loads(result)

    operator = assertion.get("operator")
    response = last_interaction


    for int in REQ_RESP:
        if int.res_id == assertion.get("sourceId"):
            response = int      
            #--> testing only interactions, get possible fixture id or variables for eval --> assert.value

    compare_val = assertion.get("value") #empty if there is none
    try:

        if "compareToSourceId" in assertion:
                if not operator:
                    operator = "equals"
                elif operator not in ["equals", "notEquals"]:
                    raise TestScriptError ("compareTo operator value not valid")
                
                if "compareToSourceExpression" in assertion and "compareToSourcePath" in assertion: 
                    raise TestScriptError("only one of [compareToSourceExpression, compareToSourcePath] can exist per Assertion")
                
                fix = None
                for int in REQ_RESP:
                    if int.res_id == assertion.get("compareToSourceId"):
                        fix = int
                for fixt in FIXTURES:
                    if fixt.source_id == assertion.get("compareToSourceId"):
                        fix = fixt

                if fix is None:
                    raise TestScriptError(f"No fixture found by compareToSourceId {assertion.get("compareToSourceId")}")
                
                if not ("value" in assertion): #  Ignored if "assert.value" is used.
                    compare_val = eval_compareTo(fix, assertion)
                    print(compare_val) #compare_val should be used by path or expression --> depends on their Operator

        if "contentType" in assertion:   
            if not operator:
                operator = "contains"
            elif operator not in ["contains", "notContains", "equals", "notEquals"]:
                raise TestScriptError("contentType operator value not valid")
            
            validate_content_type(response, assertion.get("contentType"), operator)
            log_to_file("✓ Assertion passed")
        
        elif "responseCode" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan"]:
                raise TestScriptError("responseCode operator value not valid")
            
            expected_codes = [code.strip() for code in assertion.get("responseCode", "").split(",")]
            validate_responseCode(response, expected_codes, operator)
            log_to_file("✓ Assertion passed")

        elif "response" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals"]:
                raise TestScriptError("responseCode operator value not valid")
            
            if response.reason != "":
                expected_resp = assertion.get("response")
                validate_response(response.reason, expected_resp, operator)
            else:
                raise AssertionError("No Response-display has been sent")

        if "validateProfileId" in assertion:
            msg = ""

            if PROFILES:
                #save temporary file with response
                msg = validate_profile_assertion(PROFILES.get(assertion.get("validateProfileId")), response)
            else:
                raise TestScriptError("No profiles found in testscript, but validateProfileId asserted")

            log_to_file("✓ Assertion passed\n" + msg) #--> if no Error came back
                       
        elif "resource" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals"]:
                raise TestScriptError("resource operator value not valid")
        
        elif "headerField" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan", "empty", "notEmpty", "contains", "notContains" ]:
                raise TestScriptError("headerFiedld operator value not valid")
            
        elif "navigationLinks" in assertion:
            #operator will be ignored
            raise NotImplementedError
        
        elif "expression" in assertion:
            if not operator:
                operator = "eval"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan", "empty", "notEmpty", "contains", "notContains", "eval" ]:
                raise TestScriptError("expression operator value not valid")
            
            raise NotImplementedError
        
        elif "path" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan", "empty", "notEmpty", "contains", "notContains"]:
                raise TestScriptError("expression operator value not valid")
            raise NotImplementedError

        
        if "minimumId" in assertion: #kann mit path oder expression
            #operator will be ignored
            raise NotImplementedError
        
        if "defaultManualCompletion" in assertion:
            raise TestScriptError("defaultManualCompletion is not supported as this is an automating Tool")
                
        elif assertion.get("direction") == "request" or "requestMethod" in assertion or "requestUrl" in assertion:
            log_to_file("direction request out of scope")

    except AssertionError as e:
        raise
    
# Fixture for dynamic test data
@pytest.fixture(params=get_testscript_pairs())
def testscript_data(request) -> tuple[dict,list]:
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

def execute_actions(action: dict[str, Any]) -> None:
    """
    executes any action 

    :param test: Test definition dictionary.
    :param resource: FHIR resource to test with.

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

def save_variables(variables : list) -> None:
    global VARIABLES
    for var in variables:
        id = var.get("name")

        variable = Variable(id,path=var.get("path"), 
                                  expression=var.get("expression"),
                                  sourceId=var.get("sourceId"),
                                  headerField=var.get("headerField"),
                                  defaultValue=var.get("defaultValue"))
        if id is None:
            raise TestScriptError("Variable not correctly defined!")


        if(((variable.expression is not None) & (variable.headerField is not None)) | 
           ((variable.headerField is not None) & (variable.path is not None)) | 
           ((variable.expression is not None) & (variable.path is not None))):
            raise TestScriptError(f"Variable {id} not valid Fhir, two value-expressions cannot be filled at the same time!")

        if ((variable.expression is None) & (variable.headerField is None) 
            & (variable.path is None) & (variable.defaultValue is None)):
            raise TestScriptError(f"Variable {id} is not filled!")

        VARIABLES.append(variable)

def eval_variable(var : Variable):
    global REQ_RESP
    global FIXTURES

    result = var.defaultValue or None
    expr = var.expression or None
    expr = var.path or expr
    expr = var.headerField or expr


    if (not expr) & (not result):
        raise TestScriptError("variable is not filled!")

    if expr:
        fix = None
        sourceId = var.sourceId

        for int in REQ_RESP:
            if int.res_id == sourceId:
                fix = int

        for fixture in FIXTURES:
            if fixture.source_id == sourceId:
                fix = fixture

        if var.headerField:
            if not isinstance(fix, Interaction):
                raise TypeError("Field \"headerField\" cannot be evaluated from a Fixture!")
            result = fix.header.get(expr)
            if not result:
                raise TestScriptError(f"HeaderField {var.headerField} could not be evaluated.")

        elif var.expression:
            result = do_expression(fix.body, expr)
        elif var.path:

            result = doPath(fix.body, expr)
            if isinstance(result, list):
                if len(result) == 1:
                    result = result[0]
                elif len(result) == 0:
                    raise TestScriptError("Path returned an empty result!")
                else:
                    print("error --> more than one result")

    return result
def save_fixtures(jsonFiles:list[dict], fix_list:list[dict]) -> None:
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
    
def save_profile(profilerefs : list[str], profile_ids : list[dict["id",str]]) -> None:
    #save profiles in a list full of ids and references
    global PROFILES
    for prof, pId in zip(profilerefs, profile_ids):
        PROFILES[pId.get("id")] = prof
             
def handle_assertion_error(e, stop_test_on_fail : bool):
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

def autodelete() -> None:
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
                        raise TestScriptError("Unknown Reference remaining.")
        log_to_file(f"\n ----------- Starting Setup: -----------")

        for action in setup_data.get("action", []):
            execute_actions(action)
        
        if isinstance(setup_data,dict): #if there was a setup other than autocreate
            log_to_file(f"✓ SETUP SUCCESSFUL")

    except OperationError as oe:
        raise TestScriptError("Setup operation failed: ", oe)# stop the whole testscript
    except TestExecutionError as teE:
        raise TestScriptError("Setup failed: " , teE) #stop the whole testscript
    
    except Exception as e: #usually only failure in autocreate
        raise TestScriptError("✗ TEST SKIPPED: Failure to start TestScript: " +str(e))

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
    failed = False

    try:
      
        for action in test_data.get("action" , []):
            try:
                execute_actions(action)

            #per action in test
            except OperationError as oe:
                raise TestScriptError("Test operation failed: ", oe)

            except AssertionError as ae:
                failed = True
                log_to_file("✗ Assertion failed!" + str(ae))

            except TestExecutionError as e:
                raise
                # Continue with next test even if this one was stopped

    except TestExecutionError as e:
        log_to_file(f"✗ TEST STOPPED: {test_name} - {str(e)}")
        #test schould get stopped, and next test needs to start
    finally:
        if failed:
            log_to_file(f"✗ TEST FAILED: {test_name}")
        else : 
            log_to_file(f"✓ TEST PASSED: {test_name}")
        
def TEARDOWN(teardown_data : dict):
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

    1. test server
    2. validate TS itself
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

    
        
    try:

        #validateTS(testscript) #see if the TestScript is valid
        #print("testScript is valid!") #debug message
        #--> comment so that the execution of the Tests isn't taking as much time

        #test capability
        #--> find out how important origin and destnation are

        fixture_list = get_fixture(testscript)

        variable_list = get_variables(testscript)
        

        profile_list, prof_ids = get_profile(testscript)
        # hier eine funktion die die jsonfiles von den profilen zurückgibt?
        if profile_list:
            save_profile(profile_list, prof_ids)

        if variable_list:
            save_variables(variable_list)

        if testscript.get("setup"): #there can only be one Setup
            SETUP(testscript.get("setup"),fixture_list, resources)
        else:
            SETUP({},fixture_list, resources)
            
        for test in testscript.get("test", []):
            TEST(test)  

        if testscript.get("teardown"): #there can only be one Setup
            TEARDOWN(testscript.get("teardown"))
        else:
            TEARDOWN({})

    except TestScriptError as tse:
        log_to_file("Severe error: " + str(tse))
        autodelete() #autodelete after everything went wrong
    except Exception as e:
        log_to_file("TestScript stopped! " + str(e))

    # Final summary --> find out how to save results from each test and log them

        
    FIXTURES.clear() 
    REQ_RESP.clear()
    PROFILES.clear()
    VARIABLES.clear()
