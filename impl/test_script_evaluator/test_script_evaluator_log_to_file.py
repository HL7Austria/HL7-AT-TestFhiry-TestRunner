import json
import requests
from datetime import datetime
import re
from typing import Any
from impl.exception.Error import *
from validate import *
from impl.transactions.transactions import *
from configuration_manager import get_fhir_server, get_testscript_pairs, has_fhir_server
from impl.model.fixture import Fixture
from impl.model.interaction import Interaction
from impl.model.variable import Variable
from utils import *

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
    Regex substitution callback that resolves a FHIR TestScript variable placeholder
    (e.g. ``${varName}``) to its evaluated value.

    Used as the ``repl`` argument of ``re.sub`` so that every variable reference
    inside a JSON-serialised operation or assertion is replaced with the
    concrete value before the action is executed.

    :param match: A ``re.Match`` object whose first capture group contains the variable name.
    :returns: The string value of the resolved variable.
    :raises Exception: If no variable with the given name exists in the global VARIABLES list.
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
    Executes a single FHIR TestScript operation against the configured FHIR server.

    Resolves any variable placeholders in the operation dictionary, determines the
    HTTP method (from ``method`` or by mapping the operation ``type``), builds the
    request URL, and dispatches the appropriate HTTP call (POST for create, PUT for
    update, GET for read, DELETE for delete). The server response is stored for later use.

    :param operation: Dictionary representing a single FHIR TestScript operation element.
    :raises NotImplementedError: If the operation type is not yet supported.
    :raises TestScriptError: If the HTTP method cannot be determined, or if any other
        error occurs during execution (wraps the original exception).
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
        operation_type = operation.get("type", {}).get("code", "").lower()
        url = operation.get("url")
        sourceId = operation.get("sourceId")


        #kümmere dich um die headers
        headers = {
            "Content-Type": parse_fhir_header(operation.get("contentType")),
            "Accept": parse_fhir_header(operation.get("accept")),
        }

        fixture = None

        if not method and operation_type:
            method = map_method_type(operation_type) #get method from type if exists
        if not method:
            raise TestScriptError("request method could not be found out!")
        
        if not url:
            url = build_url(operation)

        if sourceId:
            fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
            if not fixture:
                fixture = next((fix for fix in REQ_RESP if fix.res_id == sourceId), None)
            if not fixture:
                raise TestScriptError(f"Fixture {sourceId} nowhere found!")

        log_to_file(f"Executing: {operation_type.upper()} {url}")
        match (method):
            case "get":
                response = requests.get(url,headers=headers)
            case "post":
                if not fixture:
                    if not (operation_type == "search" or operation_type == "capabilities"):
                        raise TestScriptError("No Fixture found in POST!")
                    else:
                        response = requests.post(url, headers=headers)
                else:
                    response = requests.post(url, headers=headers, json=fixture.body)
            case "put":
                if not fixture:
                    raise TestScriptError("No Fixture found in PUT!")
                
                fixture.body["id"] = url.rstrip("/").split("/")[-1] #update url is [base]/[type]/[id]
                response = requests.put(url, headers=headers, json=fixture.body)
            case "delete":
                response = requests.delete(url, headers=headers)
            case "head":
                response = requests.head(url, headers=headers)
            case "patch":
                if not fixture:
                    raise TestScriptError("No Fixture found in PATCH!")
                response = requests.patch(url, headers=headers, json=fixture.body)
            case _:
                raise TestScriptError(f"Method {method} not supported.")

        if operation_type == "create":
            saved_resource_id = ""
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
                if isinstance(fixture, Fixture):
                    fixture.server_id = saved_resource_id

        log_to_file(f"Response: {response.status_code}")
    except Exception as e:
        raise TestScriptError(e)
    
    

    int_id = operation.get("responseId")
    global last_interaction
    last_interaction = Interaction(response.headers, response.text)
    last_interaction.status_code = response.status_code
    last_interaction.reason = response.reason
    last_interaction.res_id = int_id
    

    if(int_id != None):
        REQ_RESP.append(last_interaction)

def build_url(operation :dict [str, Any]) -> str:
    """
    Constructs the full request URL for a FHIR TestScript operation when no
    explicit ``url`` field is provided.

    Combines the FHIR server base URL with the operation's ``resource``,
    ``params``, ``sourceId``, and ``targetId`` fields according to the FHIR
    TestScript specification rules.  Special cases such as ``transaction``
    (base URL only) and ``capabilities`` (``/metadata``) are handled
    separately.

    :param operation: Dictionary representing a single FHIR TestScript operation element.
    :returns: The fully constructed URL string.
    :raises TestScriptError: If required fields are missing or if the combination of
        fields violates the FHIR TestScript specification (e.g. ``params`` on a
        create, ``targetId`` on a search, unknown references).
    :raises OperationError: If a ``vread`` operation is requested but no version ID
        can be found.
    :raises Exception: If the fixture body is in XML format, which is not yet supported.
    """
    url = FHIR_SERVER_BASE
    params = operation.get("params")
    sourceId = operation.get("sourceId")
    targetId = operation.get("targetId")
    resource = operation.get("resource")
    type = operation.get("type", {}).get("code", "").lower()

    if targetId and type == "search":
        raise TestScriptError("targetId should not be used with search.")
    if targetId and type == "create":
        raise TestScriptError("Create should not have a targetId")
    if params and (type == "create" or type == "transaction"):
        raise TestScriptError("Create and transaction should not have params!")

    fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
    if not fixture:
        fixture = next((fix for fix in REQ_RESP if fix.res_id == sourceId), None)
    Tfixture = next((fix for fix in FIXTURES if fix.source_id == targetId), None)
    if not Tfixture:
        Tfixture = next((fix for fix in REQ_RESP if fix.res_id == targetId), None)
    #--> suchen der Fixture wenn leer = None

    if type == "transaction" or type == "batch":
        return url
    elif type == "capabilities" and not params:
        return url + "/metadata"

    if params:
        if type == "read" or type == "vread" or type == "update" or type == "delete":
            if not resource:
                raise TestScriptError(f"Resource-Type is needed for Operation {type} {params}")
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
                return url +  "/" + url_type +  "/" + id + "/_history" +  "/" + vid
            elif type == "history":
                return url +  "/" + url_type +  "/" + id + "/_history"
            else:
                if type == "update" and sourceId:
                    return url +  "/" + id
                else:
                    return url +  "/" + url_type +  "/" + id
        return url

def execute_assertion(assertion : dict[str,Any]) -> None:
    """
    Evaluates a single FHIR TestScript assertion against the most recent server
    interaction (or an explicitly referenced interaction/fixture).

    Resolves variable placeholders in the assertion, selects the correct
    operator and response to compare against, and delegates to the appropriate
    validation function (content-type, response code, response display, profile,
    etc.).  If the assertion passes, the result is logged; if it fails, an
    ``AssertionError`` is raised and re-raised to the caller.

    :param assertion: Dictionary representing a single FHIR TestScript assert element.
    :raises AssertionError: If the assertion check fails.
    :raises TestScriptError: If the operator is invalid for the given assertion type,
        if mutually exclusive fields are both present, or if a required fixture /
        profile cannot be found.
    :raises NotImplementedError: If the assertion type (e.g. navigationLinks,
        expression, path, minimumId) is not yet implemented.
    """
    global last_interaction
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
                
                if not("expression" in assertion or "path" in assertion):
                    raise TestScriptError("CompareTo is only valid with expression or path!")
                
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
                    #compare_val should be used by path or expression --> depends on their Operator

        if "contentType" in assertion:   
            if not operator:
                operator = "contains"
            elif operator not in ["contains", "notContains", "equals", "notEquals"]:
                raise TestScriptError("contentType operator value not valid")
            
            validate_content_type(response, assertion.get("contentType"), operator)
        
        elif "responseCode" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan"]:
                raise TestScriptError("responseCode operator value not valid")
            
            expected_codes = [code.strip() for code in assertion.get("responseCode", "").split(",")]
            validate_responseCode(response, expected_codes, operator)

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
                       
        elif "resource" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals"]:
                raise TestScriptError("resource operator value not valid")
        
        elif "headerField" in assertion:
            #mit value
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
            validate_expression(response, assertion.get("expression"), operator, compare_val)
        
        elif "path" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan", "empty", "notEmpty", "contains", "notContains"]:
                raise TestScriptError("path operator value not valid")
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
    
def load_testscript_data(testscript_path, resource_path) -> tuple[dict,list]:
    """
    Loads testscript and resource data for a given pair of paths.

    :param testscript_path: Path to the TestScript JSON file.
    :param resource_path: Path to the resource JSON file(s), or None.
    :return: Tuple of (testscript, resources) data.
    """
    testscript = load_json(testscript_path)
    if resource_path:
        resources = load_json_list(resource_path)
    else:
        resources = None
    return testscript, resources

def execute_actions(action: dict[str, Any]) -> None:
    """
    Dispatches a single FHIR TestScript action — either an operation or an
    assertion — to the corresponding execution function.

    Acts as the central routing point for every action inside the setup, test,
    and teardown phases of a TestScript.  When an assertion carries
    ``stopTestOnFail`` set to false, a failing assertion is logged but does not
    abort the current test; otherwise the error propagates.

    :param action: Dictionary representing one action element from a FHIR
        TestScript phase (must contain either an ``operation`` or ``assert`` key).
    :raises AssertionError: Re-raised when an assertion fails and
        ``stopTestOnFail`` is not false.
    :raises TestExecutionError: If the operation or assertion raises any
        non-assertion exception, wrapped with context.
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
            log_to_file("✓ Assertion passed\n")
        
    except AssertionError as ae:
        if not stopTestOnFail:
            handle_assertion_error(ae, stopTestOnFail)
        raise        
    except Exception as e:
        raise TestExecutionError(f"Test stopped: {str(e)}")

def save_variables(variables : list) -> None:
    """
    Parses and stores FHIR TestScript variable definitions into the global
    ``VARIABLES`` list so they can be resolved during operation and assertion
    execution.

    Each variable must have a ``name`` and exactly one value source (``path``,
    ``expression``, ``headerField``, or ``defaultValue``).  The function
    validates these constraints before appending.

    :param variables: List of raw variable dictionaries from the TestScript JSON.
    :raises TestScriptError: If a variable has no ``name``, if more than one
        value-expression field is set simultaneously, or if no value source is
        provided at all.
    """
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
    """
    Resolves a single FHIR TestScript variable to its concrete value.

    Looks up the referenced fixture or interaction via ``sourceId`` and
    evaluates the variable's value source (``headerField``, ``expression``,
    or ``path``).  Falls back to ``defaultValue`` when no expression-based
    source is defined.

    :param var: A ``Variable`` instance holding the variable definition.
    :returns: The resolved value as a string (or the type returned by the
        expression / path evaluator).
    :raises TestScriptError: If the variable has no value source at all, if a
        header field cannot be found on the interaction, or if a path evaluation
        returns an empty result.
    :raises TypeError: If ``headerField`` is used but the referenced source is
        a static ``Fixture`` instead of a server ``Interaction``.
    """
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
            if isinstance(result, list):
                if len(result) == 1:
                    result = result[0]
                elif len(result) == 0:
                    raise TestScriptError("Expression returnded an empty result")
                else:
                    raise TestScriptError("More than one result!")
        elif var.path:

            result = doPath(fix.body, expr)
            if isinstance(result, list):
                if len(result) == 1:
                    result = result[0]
                elif len(result) == 0:
                    raise TestScriptError("Path returned an empty result!")
                else:
                    raise TestScriptError("More than one result!")

    return result
def save_fixtures(jsonFiles:list[dict], fix_list:list[dict]) -> None:
    """
    Registers FHIR TestScript fixtures locally and, for those marked with
    ``autocreate``, uploads them to the FHIR server as a transaction bundle.

    Each fixture is stored in the global ``FIXTURES`` list.  Fixtures whose
    ``autocreate`` flag is true are bundled into a single FHIR transaction
    POST.  After a successful upload the server-assigned IDs are written back
    into the corresponding ``Fixture`` objects so that later operations and
    assertions can reference them.

    :param jsonFiles: List of parsed JSON bodies of the Example Instance files
        (one per fixture).
    :param fix_list: List of raw fixture definition dictionaries from the
        TestScript JSON (parallel to ``jsonFiles``).
    :raises Exception: If the transaction bundle POST fails, with the
        diagnostic messages extracted from the server's OperationOutcome.
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
    
def save_profile(profilerefs : list[str], profile_ids : list[dict[str,str]]) -> None:
    """
    Stores FHIR StructureDefinition profile references in the global
    ``PROFILES`` dictionary, keyed by their TestScript-local ID.

    :param profilerefs: List of profile canonical URL references.
    :param profile_ids: List of dictionaries each containing an ``id`` key
        that serves as the TestScript-local identifier for the profile.
    """
    global PROFILES
    for prof, pId in zip(profilerefs, profile_ids):
        PROFILES[pId.get("id")] = prof
             
def handle_assertion_error(e, stop_test_on_fail : bool):
    """
    Logs a failed assertion and decides whether the current test should be
    aborted or is allowed to continue.

    Called when an ``AssertionError`` is caught inside ``execute_actions``.
    If ``stop_test_on_fail`` is ``False`` the error is escalated to a
    ``TestExecutionError`` so the caller can halt; otherwise the failure is
    only recorded and execution may proceed.

    :param e: The ``AssertionError`` exception that was raised.
    :param stop_test_on_fail: When ``False``, the test must be stopped;
        when ``True``, execution may continue despite the failure.
    :returns: ``False`` to signal that the assertion failed but continuing
        is allowed.
    :raises TestExecutionError: If ``stop_test_on_fail`` is ``False``,
        indicating the test must not continue.
    """
    log_to_file(f"✗ ASSERTION FAILED: {str(e)}")
    if stop_test_on_fail == False:
        raise TestExecutionError(f"Test stopped due to stopTestOnFail: {str(e)}")
    return False  # Test failed, but continuing allowed

def autodelete() -> None:
        """
        Deletes every fixture from the FHIR server whose ``autodelete`` flag
        is ``True`` and that was successfully created (i.e. has a non-empty
        ``server_id``).
        """
        global FIXTURES
        for fix in FIXTURES:
            if fix.autodelete and fix.server_id != "":
                requests.delete(f"{FHIR_SERVER_BASE}/{fix.type}/{fix.server_id}")

def SETUP(setup_data, fixture_list : list, resources):
    """
    Executes the **setup** phase of a FHIR TestScript.

    Creates fixtures on the server (autocreate), rewrites inter-fixture
    references so they point to server-assigned IDs, and then runs every
    setup action in order.

    :param setup_data: The ``setup`` dictionary from the TestScript JSON,
        or an empty dict when there is no explicit setup section.
    :param fixture_list: List of raw fixture definition dictionaries from
        the TestScript.
    :param resources: List of parsed JSON bodies of the Example Instance
        files that back the fixtures.
    :raises TestScriptError: If a setup operation fails
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

                if re.search("\"reference\" *: *\"[a-zA-Z]*/[a-zA-Z-]+", json.dumps(fix1.body)) != None: #look again to make sure no unattended references exist
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
    Executes a single **test** phase of a FHIR TestScript.

    Iterates over all actions defined in the test.
    Assertion failures are logged and flagged but do not necessarily
    abort the remaining actions; a ``TestExecutionError`` (e.g. from
    ``stopTestOnFail``) does stop the test.  The overall pass/fail result
    is logged after all actions have been attempted.

    :param test_data: A single ``test`` element dictionary from the
        TestScript JSON.
    :raises TestScriptError: If an operation within the test fails
        (wraps ``OperationError``).
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
    """
    Executes the **teardown** phase of a FHIR TestScript.

    Runs every teardown action (operations and assertions) and afterwards
    calls ``autodelete`` to remove all fixtures whose ``autodelete`` flag
    is set.

    :param teardown_data: The ``teardown`` dictionary from the TestScript
        JSON, or an empty dict when there is no explicit teardown section.
    :raises TestScriptError: If a teardown operation fails
        (wraps ``OperationError``).
    """
    try:
        for action in teardown_data.get("action", []):
            execute_actions(action)
        
        autodelete()
        
    except OperationError as oe:
        raise TestScriptError("Teardown operation failed: " , oe)

def test_fhir_operations(testscript_data):
    """
    Main pytest entry point that orchestrates a complete FHIR TestScript run.

    Extracts fixtures, variables, and profiles from the TestScript, then
    drives execution through the three TestScript phases in order:
    **SETUP** → **TEST** → **TEARDOWN**.  On severe errors
    the run is aborted and ``autodelete`` is invoked to clean up
    server-side resources.  All global state (``FIXTURES``, ``REQ_RESP``,
    ``PROFILES``, ``VARIABLES``) is cleared at the end regardless of
    outcome.

    :param testscript_data: Tuple of ``(testscript_dict, resources_list)``
        as provided by the ``testscript_data`` pytest fixture.
    :raises pytest.skip: If no FHIR server is configured.
    """

    if not has_fhir_server():
        log_to_file("✗ TEST SKIPPED: No FHIR server configured")
        return
    
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

if __name__ == "__main__":
    for testscript_path, resource_path in get_testscript_pairs():
        testscript_data = load_testscript_data(testscript_path, resource_path)
        test_fhir_operations(testscript_data)
