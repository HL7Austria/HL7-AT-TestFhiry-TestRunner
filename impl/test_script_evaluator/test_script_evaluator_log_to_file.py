import json
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

from requests.utils import requote_uri

import impl.test_script_evaluator.configuration_manager as conf_man
import impl.exception.Error as error
from impl.model.fixture import Fixture
from impl.model.interaction import Interaction
from impl.model.variable import Variable
import impl.test_script_evaluator.validate as validate
import impl.test_script_evaluator.utils as utils
import impl.test_script_evaluator.reference_parser as reference_parser
import impl.test_script_evaluator.dependency_resolver as dependency_resolver
import impl.test_script_evaluator.result_tracker as rt
import impl.test_script_evaluator.communication_logger as comm_log

log = logging.getLogger("testrunner.executor")

last_interaction = None
asserted_interaction = None # interaction the last assertion was evaluated against

FIXTURES = [] # static Fixtures
REQ_RESP = [] # responses
VARIABLES = []
PROFILES = {} #saving profilesIDs with the references

FHIR_SERVER_BASE: str = ""

def replacer(match) -> str:
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
    for var in VARIABLES:
        if var.name == var_name:
            return str(eval_variable(var))
    
    raise Exception(f"Variable {var_name} could not be found")

VARIABLE_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

def resolve_variables(element: dict[str, Any]) -> dict[str, Any]:
    """
    Replaces every variable placeholder (``${varName}``) in an operation or
    assertion with the value of the variable and logs the values used.

    :param element: Operation or assert dictionary from the TestScript.
    :returns: A copy of ``element`` with the variables replaced.
    """
    json_str = json.dumps(element)
    values = {}
    def resolve(match) -> str:
        if match.group(1) not in values:
            values[match.group(1)] = replacer(match)
        return values[match.group(1)]
    result = VARIABLE_PATTERN.sub(resolve, json_str)
    for name, value in values.items():
        log.debug("Variable ${%s} = '%s'", name, value)
    return json.loads(result)

def execute_operation(operation: dict[str, Any]) -> None:
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
        operation = resolve_variables(operation)

        #get all Info from operation
        method = operation.get("method")
        operation_type = operation.get("type", {}).get("code", "").lower()
        url = operation.get("url")
        sourceId = operation.get("sourceId")

        headers = {}
        reqHeader = operation.get("requestHeader")

        if operation.get("contentType"):
            headers["Content-Type"]= operation.get("contentType")
        if operation.get("accept"):
            headers["Accept"] = operation.get("accept")
        if reqHeader:
            for head in reqHeader:
                headers[head.get("field")] = head.get("value")
        
        fixture = None

        if not method and operation_type:
            method = utils.map_method_type(operation_type) #get method from type if exists
        if not method:
            raise error.TestScriptError("request method could not be found out!")
        
        if not url:
            url = build_url(operation)

        if operation.get("encodeRequestUrl") == True:
            # percent-encode what is not encoded yet; keeps the delimiters (?, &, =) and existing %XX escapes
            url = requote_uri(url)

        log.info("Operation %s", _describe_operation(operation, method))
        if operation.get("description"):
            log.debug("Operation description: %s", operation["description"])

        if sourceId:
            fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
            if not fixture:
                fixture = next((fix for fix in REQ_RESP if fix.res_id == sourceId), None)
            if not fixture:
                raise error.TestScriptError(f"Fixture {sourceId} nowhere found!")
            
            # Validate that fixture has all references resolved before using as sourceId
            if isinstance(fixture, Fixture) and not fixture.references_resolved:
                raise error.TestScriptError(
                    f"Fixture {sourceId} has unresolved references and cannot be used as sourceId. "
                    f"Unresolved references: {fixture.references}"
                )

        match (method):
            case "get":
                request_id, response = comm_log.send_request("get", url, headers)
            case "post":
                if not fixture:
                    if not (operation_type == "search" or operation_type == "capabilities"):
                        raise error.TestScriptError("No Fixture found in POST!")
                    else:
                        request_id, response = comm_log.send_request("post", url, headers)
                else:
                    body_data = json.dumps(fixture.body) if utils.string_type(fixture.body) == "json" else fixture.body
                    request_id, response = comm_log.send_request("post", url, headers, body_data)
            case "put":
                if not fixture:
                    raise error.TestScriptError("No Fixture found in PUT!")
                
                update_id = url.rstrip("/").split("/")[-1] #update url is [base]/[type]/[id]
                if utils.string_type(fixture.body) == "json":
                    if isinstance(fixture.body, str):
                        fixture.body = json.loads(fixture.body)
                    fixture.body["id"] = update_id
                    body_data = json.dumps(fixture.body)
                else:
                    fixture.body = re.sub(r'(<id[^>]*value=")[^"]*("/>)', r'\g<1>' + update_id + r'\g<2>', fixture.body)
                    body_data = fixture.body
                request_id, response = comm_log.send_request("put", url, headers, body_data)
            case "delete":
                request_id, response = comm_log.send_request("delete", url, headers)
            case "head":
                request_id, response = comm_log.send_request("head", url, headers)
            case "patch":
                if not fixture:
                    raise error.TestScriptError("No Fixture found in PATCH!")
                body_data = json.dumps(fixture.body) if utils.string_type(fixture.body) == "json" else fixture.body
                request_id, response = comm_log.send_request("patch", url, headers, body_data)
            case _:
                raise error.TestScriptError(f"Method {method} not supported.")

        if operation_type == "create":
            # Surface the real server error instead of a misleading "No ID found"
            # message when the create is rejected (e.g. validation / referential
            # integrity errors returned as a non-2xx OperationOutcome).
            if not (200 <= response.status_code < 300):
                raise error.TestScriptError(
                    f"Create operation failed ({request_id}): HTTP {response.status_code} {response.reason} - "
                    f"{response.text[:500]}"
                )
            saved_resource_id = ""
            location = response.headers.get("Location", "")
            if location:
                parts = location.rstrip("/").split("/")
                if "_history" in parts:
                    # ID ist der Teil vor _history
                    history_idx = parts.index("_history")
                    saved_resource_id = parts[history_idx - 1]
                else:
                    # ID ist der letzte Teil
                    saved_resource_id = parts[-1]
            else:
                try:
                    saved_resource_id = response.json().get("id")
                except ValueError:
                    root = ET.fromstring(response.text)
                    ns = {'fhir': 'http://hl7.org/fhir'}
                    id_el = root.find('fhir:id', ns) if '}' in root.tag else root.find('id')
                    saved_resource_id = id_el.get('value', '') if id_el is not None else ''
                if not saved_resource_id:
                    raise ValueError("No ID found in response or Location header")
            if isinstance(fixture, Fixture):
                fixture.server_id = saved_resource_id
            log.debug("%s created resource id '%s'", request_id, saved_resource_id)
    except error.TestScriptError:
        raise
    except Exception as e:
        raise error.TestScriptError(str(e) or type(e).__name__) from e
    
    

    int_id = operation.get("responseId")
    global last_interaction
    last_interaction = Interaction(response.headers, response.text)
    last_interaction.status_code = response.status_code
    last_interaction.reason = response.reason
    last_interaction.res_id = int_id
    last_interaction.request_id = request_id
    

    if int_id != None:
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
    op_type = operation.get("type", {}).get("code", "").lower()

    if targetId and op_type == "search":
        raise error.TestScriptError("targetId should not be used with search.")
    if targetId and op_type == "create":
        raise error.TestScriptError("Create should not have a targetId")
    if params and (op_type == "create" or op_type == "transaction"):
        raise error.TestScriptError("Create and transaction should not have params!")

    fixture = next((fix for fix in FIXTURES if fix.source_id == sourceId), None)
    if not fixture:
        fixture = next((fix for fix in REQ_RESP if fix.res_id == sourceId), None)
    Tfixture = next((fix for fix in FIXTURES if fix.source_id == targetId), None)
    if not Tfixture:
        Tfixture = next((fix for fix in REQ_RESP if fix.res_id == targetId), None)
    #--> checks to see if the ourceId is in the saved static Fixtures or responses

    if op_type == "transaction" or op_type == "batch":
        return url
    elif op_type == "capabilities" and not params:
        return url + "/metadata"

    if params:
        if op_type == "read" or op_type == "vread" or op_type == "update" or op_type == "delete":
            if not resource:
                raise error.TestScriptError(f"Resource-Type is needed for Operation {op_type} {params}")
        if resource:
            url += "/" + resource
        # params is the path after [type] and starts with "/" or "?" ("/[id]", "?name=value");
        # a bare "[id]" still gets its separator
        if not params.startswith(("/", "?")):
            params = "/" + params
        return url + params
    else:
        if not op_type:
            raise error.TestScriptError("Could not create url for Operation!")
        
        if sourceId:
            if not fixture:
                raise error.TestScriptError(f"Fixture {sourceId} could not be found")
            if isinstance(fixture, Fixture):
                if fixture.type:
                    url += "/" + fixture.type
            else:
                _, res_type = utils.extract_fhir_meta(fixture.body)
                if res_type:
                    url += "/" + res_type
        
        if targetId:
            res_id = ""
            vid = ""
            url_type = ""
            if isinstance(Tfixture, Interaction):
                if "Location" in Tfixture.header:
                    location = Tfixture.header.get("Location")
                    if "_history" in location:
                        res_id = location.rstrip("/").split("/")[-3]
                        vid = location.rstrip("/").split("/")[-1]
                    else:
                        res_id = location.rstrip("/").split("/")[-1]
                else:
                    if utils.string_type(Tfixture.body) == "json":
                        body = json.loads(Tfixture.body) if isinstance(Tfixture.body, str) else Tfixture.body
                        res_id = body.get("id")
                        meta = body.get("meta")
                        vid = meta.get("versionId") if meta else ""
                    else:
                        root = ET.fromstring(Tfixture.body)
                        ns_match = root.tag.split('}')[0] + '}' if '{' in root.tag else ''
                        ns = {'ns': ns_match.strip('{}')} if ns_match else {}
                        if ns:
                            id_el = root.find('ns:id', ns)
                            meta_el = root.find('ns:meta/ns:versionId', ns)
                        else:
                            id_el = root.find('id')
                            meta_el = root.find('meta/versionId')
                        res_id = id_el.get('value', '') if id_el is not None else ''
                        vid = meta_el.get('value', '') if meta_el is not None else ''
            elif isinstance(Tfixture, Fixture):
                res_id = Tfixture.server_id
            else:
                raise error.TestScriptError(f"Fixture {targetId} not found!")
            
            if isinstance(Tfixture, Fixture):
                url_type = Tfixture.type
            elif utils.string_type(Tfixture.body) == "json":
                body = json.loads(Tfixture.body) if isinstance(Tfixture.body, str) else Tfixture.body
                url_type = body.get("resourceType")
            else:
                root = ET.fromstring(Tfixture.body)
                url_type = root.tag.split('}')[-1] if '}' in root.tag else root.tag
            
            if op_type == "vread":
                if vid == "":
                    raise error.OperationError("No versonId found for vread Operation.")
                return url +  "/" + url_type +  "/" + res_id + "/_history" +  "/" + vid
            elif op_type == "history":
                return url +  "/" + url_type +  "/" + res_id + "/_history"
            else:
                if op_type == "update" and sourceId:
                    return url +  "/" + res_id
                else:
                    return url +  "/" + url_type +  "/" + res_id
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
    global asserted_interaction
    global REQ_RESP

    asserted_interaction = None
    #--> not checking if the variable is at the right place!
    assertion = resolve_variables(assertion)

    operator = assertion.get("operator")
    response = last_interaction


    for int in REQ_RESP:
        if int.res_id == assertion.get("sourceId"):
            response = int      
            #--> testing only interactions, get possible fixture id or variables for eval --> assert.value

    if response is None:
        raise error.TestScriptError("No response to assert against: no operation has been executed yet")
    asserted_interaction = response

    compare_val = assertion.get("value") #empty if there is none
    try:

        if "compareToSourceId" in assertion:
                if not operator:
                    operator = "equals"
                elif operator not in ["equals", "notEquals"]:
                    raise error.TestScriptError ("compareTo operator value not valid")
                
                if "compareToSourceExpression" in assertion and "compareToSourcePath" in assertion: 
                    raise error.TestScriptError("only one of [compareToSourceExpression, compareToSourcePath] can exist per Assertion")
                
                if not("expression" in assertion or "path" in assertion):
                    raise error.TestScriptError("CompareTo is only valid with expression or path!")
                
                fix = None
                #check to see if the compareToSourceId is in the saved static Fixtures or responses
                for int in REQ_RESP:
                    if int.res_id == assertion.get("compareToSourceId"):
                        fix = int
                for fixt in FIXTURES:
                    if fixt.source_id == assertion.get("compareToSourceId"):
                        fix = fixt

                if fix is None:
                    raise error.TestScriptError(f"No fixture found by compareToSourceId {assertion.get('compareToSourceId')}")
                
                if not ("value" in assertion): #  Ignored if "assert.value" is used.
                    compare_val = validate.eval_compareTo(fix, assertion)
                    #compare_val should be used by path or expression --> depends on their Operator

        if "contentType" in assertion:   
            if not operator:
                operator = "contains"
            elif operator not in ["contains", "notContains", "equals", "notEquals"]:
                raise error.TestScriptError("contentType operator value not valid")
            
            validate.validate_content_type(response, assertion.get("contentType"), operator)
        
        elif "responseCode" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan"]:
                raise error.TestScriptError("responseCode operator value not valid")
            
            expected_codes = [code.strip() for code in assertion.get("responseCode", "").split(",")]
            validate.validate_responseCode(response, expected_codes, operator)

        elif "response" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals"]:
                raise error.TestScriptError("responseCode operator value not valid")
            
            expected_resp = assertion.get("response")
            validate.validate_response(response, expected_resp, operator)

        if "validateProfileId" in assertion:
            msg = ""
            if PROFILES:
                profile_ref = PROFILES.get(assertion["validateProfileId"])
                if not profile_ref:
                    raise AssertionError(f"Profile {assertion['validateProfileId']} not found in testscript")
                msg = validate.validate_profile_assertion(profile_ref, response)
                if msg.strip():
                    log.debug("Validator warnings and information:%s", msg.rstrip())
            else:
                raise AssertionError("No profiles found in testscript, but validateProfileId asserted")
                       
        elif "resource" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals"]:
                raise error.TestScriptError("resource operator value not valid")
            validate.validate_resource(response, assertion["resource"], operator)
        
        elif "headerField" in assertion:
            #mit value
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan", "empty", "notEmpty", "contains", "notContains" ]:
                raise error.TestScriptError("headerFiedld operator value not valid")
            validate.validate_headerfield(response, assertion["headerField"], compare_val, operator)
            
        elif "navigationLinks" in assertion:
            #operator will be ignored
            """
            check if bundle
            check if first, last and next links
            --> Error needs to reflect what is missing
            """
            raise NotImplementedError("navigationLinks assertions are not supported yet")
        
        elif "expression" in assertion:
            if not operator:
                operator = "eval"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan", "empty", "notEmpty", "contains", "notContains", "eval" ]:
                raise error.TestScriptError("expression operator value not valid")
            validate.validate_expression(response, assertion["expression"], operator, compare_val)
        
        elif "path" in assertion:
            if not operator:
                operator = "equals"
            elif operator not in ["equals", "notEquals", "in", "notIn", "greaterThan", "lessThan", "empty", "notEmpty", "contains", "notContains"]:
                raise error.TestScriptError("path operator value not valid")
            validate.validate_path(response, assertion["path"], compare_val, operator)

        
        if "minimumId" in assertion:
            #operator will be ignored
            """
            find a way to check if this static fixture or previous response is inside the response
            --> find out if there is a library, find out if validator has that
            """
            raise NotImplementedError("minimumId assertions are not supported yet")
        
        if "defaultManualCompletion" in assertion:
            raise error.TestScriptError("defaultManualCompletion is not supported as this is an automating Tool")
                
        elif assertion.get("direction") == "request" or "requestMethod" in assertion or "requestUrl" in assertion:
            raise error.TestScriptError("Direction request out of scope")

    except AssertionError as e:
        raise
    
def load_testscript_data(testscript_path, resource_path) -> tuple[dict,list]:
    """
    Loads testscript and resource data for a given pair of paths.

    :param testscript_path: Path to the TestScript JSON file.
    :param resource_path: Path to the resource file(s) (JSON or XML), or None.
    :return: Tuple of (testscript, resources) data.
    """
    testscript = utils.load_json(testscript_path)
    resources = utils.load_resource_list(resource_path) if resource_path else []
    return testscript, resources

def execute_actions(action: dict[str, Any]) -> None:
    """
    Dispatches a single FHIR TestScript action — either an operation or an
    assertion — to the corresponding execution function.

    Acts as the central routing point for every action inside the setup, test,
    and teardown phases of a TestScript.  A failing assertion is handled
    according to its flags:

    * ``warningOnly`` true: reported as a warning, the test continues.
    * ``stopTestOnFail`` true: the current test stops (the remaining tests
      and the teardown still run).
    * ``stopTestOnFail`` false or missing: the failure is recorded and the
      test continues with its remaining actions.

    ``stopTestOnFail`` follows the element's short name and definition
    ("If this assert fails, will the current test execution stop?").  The
    R5 spec details comments section says the opposite, but it is a copy of the
    ``warningOnly`` comment and is treated as a spec error.  R4 does not have
    the element, so a missing flag means "continue".

    :param action: Dictionary representing one action element from a FHIR
        TestScript phase (must contain either an ``operation`` or ``assert`` key).
    :raises WarningException: If a ``warningOnly`` assertion fails.
    :raises AssertionError: If an assertion with ``stopTestOnFail`` true fails.
    :raises AssertionFailedContinueError: If an assertion with
        ``stopTestOnFail`` false or missing fails.
    :raises TestExecutionError: If the operation or assertion could not be
        executed (invalid TestScript, unsupported feature, connection or
        validator problem).  The original exception is kept as ``__cause__``.
    """

    try:
        # WHEN – Operation
        if "operation" in action:
            operation = action["operation"]
            execute_operation(operation)

         # THEN - Assertion
        elif "assert" in action:
            assertion = action["assert"]
            if assertion.get("description"):
                log.debug("Assert description: %s", assertion["description"])
            execute_assertion(assertion)
            log.info("Assert passed: %s%s", _describe_assertion(assertion), _request_ref())

    except AssertionError as ae:
        warningOnly = action.get("assert", {}).get("warningOnly", False)
        stopTestOnFail = action.get("assert", {}).get("stopTestOnFail", False)
        # Convert string values to boolean for robust comparison
        if isinstance(warningOnly, str):
            warningOnly = warningOnly.lower() == "true"
        if isinstance(stopTestOnFail, str):
            stopTestOnFail = stopTestOnFail.lower() == "true"

        description = _describe_assertion(action.get("assert", {}))
        if warningOnly:
            # Log warning but continue test
            log.warning("Assert failed (warningOnly): %s%s - %s", description, _request_ref(), ae)
            raise error.WarningException(str(ae))
        elif stopTestOnFail:
            # stopTestOnFail is true - stop the current test
            log.error("Assert failed (stopTestOnFail): %s%s - %s", description, _request_ref(), ae)
            raise AssertionError(f"Assertion failed (stopTestOnFail): {str(ae)}") from ae
        else:
            # stopTestOnFail is false or missing - record the failure, continue with remaining actions
            log.error("Assert failed: %s%s - %s", description, _request_ref(), ae)
            raise error.AssertionFailedContinueError(f"Assertion failed: {str(ae)}")
    except error.WarningException as we:
        log.warning("Assert not checked: %s - %s", _describe_assertion(action.get("assert", {})), we)
        raise

    except Exception as e:
        kind = "Assert" if "assert" in action else "Operation"
        log.error("%s could not be executed (%s): %s", kind, _error_cause(e), str(e) or type(e).__name__)
        log.debug("Traceback:", exc_info=True)
        raise error.TestExecutionError(str(e) or type(e).__name__) from e

def _describe_operation(operation: dict[str, Any], method: str) -> str:
    """
    Short description of an operation for the log, e.g.
    ``create Patient (POST, sourceId patient-create, responseId create-response)``.
    """
    op_type = operation.get("type", {}).get("code") or "operation"
    text = f"{op_type} {operation.get('resource') or ''}".strip()
    details = [method.upper()]
    for field in ("sourceId", "targetId", "params", "responseId", "requestId"):
        if operation.get(field):
            details.append(f"{field} {operation[field]}")
    return f"{text} ({', '.join(details)})"

def _describe_assertion(assertion: dict[str, Any]) -> str:
    """
    Short description of an assertion for the log, e.g. ``responseCode in '200,201'``
    or ``expression 'Patient.id' equals 'abc' on read-response``.
    """
    operator = assertion.get("operator")
    checks = []
    for check in ("responseCode", "response", "contentType", "resource"):
        if check in assertion:
            checks.append(" ".join(filter(None, [check, operator, f"'{assertion[check]}'"])))
    for check in ("validateProfileId", "headerField", "expression", "path", "minimumId", "navigationLinks"):
        if check in assertion:
            text = " ".join(filter(None, [f"{check} '{assertion[check]}'", operator]))
            if "value" in assertion:
                text += f" '{assertion['value']}'"
            elif "compareToSourceId" in assertion:
                text += f" {assertion['compareToSourceId']}"
            checks.append(text)
    if not checks:
        return assertion.get("label") or assertion.get("description") or "assertion"
    text = ", ".join(checks)
    if assertion.get("sourceId"):
        text += f" on {assertion['sourceId']}"
    return text

def _request_ref() -> str:
    """Reference to the communication log of the response the last assertion was evaluated against."""
    request_id = getattr(asserted_interaction, "request_id", None)
    return f" [{request_id}]" if request_id else ""

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
        var_id = var.get("name")

        variable = Variable(var_id,path=var.get("path"), 
                                  expression=var.get("expression"),
                                  sourceId=var.get("sourceId"),
                                  headerField=var.get("headerField"),
                                  defaultValue=var.get("defaultValue"))
        if var_id is None:
            raise error.TestScriptError("Variable not correctly defined!")


        if ((variable.expression is not None and variable.headerField is not None) or 
           (variable.headerField is not None and variable.path is not None) or 
           (variable.expression is not None and variable.path is not None)):
            raise error.TestScriptError(f"Variable {var_id} not valid Fhir, two value-expressions cannot be filled at the same time!")

        if (variable.expression is None and variable.headerField is None 
            and variable.path is None and variable.defaultValue is None):
            raise error.TestScriptError(f"Variable {var_id} is not filled!")

        VARIABLES.append(variable)
        log.debug("Variable %s defined (%s)", var_id, _variable_source(variable))

def _variable_source(variable: Variable) -> str:
    """Where the value of a variable comes from, for the log."""
    for field in ("expression", "path", "headerField"):
        if getattr(variable, field) is not None:
            return f"{field} '{getattr(variable, field)}' on {variable.sourceId}"
    return f"defaultValue '{variable.defaultValue}'"

def eval_variable(var : Variable):
    """
    Resolves a single FHIR TestScript variable to its concrete value.

    Looks up the referenced static fixture or interaction via ``sourceId`` and
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
        raise error.TestScriptError("variable is not filled!")

    if expr:
        fix = None
        sourceId = var.sourceId

        #check if the sourceId is in the saved static Fixtures or responses
        for int in REQ_RESP:
            if int.res_id == sourceId:
                fix = int

        for fixture in FIXTURES:
            if fixture.source_id == sourceId:
                fix = fixture

        if fix is None:
            raise error.TestScriptError(f"Variable {var.name}: no fixture or response found for sourceId {sourceId}")

        if var.headerField:
            if not isinstance(fix, Interaction):
                raise TypeError("Field \"headerField\" cannot be evaluated from a Fixture!")
            result = fix.header.get(expr)
            if not result:
                raise error.TestScriptError(f"HeaderField {var.headerField} could not be evaluated.")

        elif var.expression:
            if utils.string_type(fix.body) == "json":
                body_use = json.loads(fix.body) if isinstance(fix.body, str) else fix.body
            elif utils.string_type(fix.body) == "xml":
                # XML zu JSON konvertieren für FHIRPath
                body_use = validate.convert_xml_to_json(fix.body) if isinstance(fix.body, str) else fix.body
            else:
                raise error.TestScriptError("FHIRPath expression cannot be evaluated on this body type.")
            result = validate.eval_expression(body_use, expr)
            if isinstance(result, list):
                if len(result) == 1:
                    result = result[0]
                elif len(result) == 0:
                    raise error.TestScriptError("Expression returnded an empty result")
                else:
                    raise error.TestScriptError("More than one result!")
        elif var.path:

            result = validate.eval_path(fix.body, expr)
            if isinstance(result, list):
                if len(result) == 1:
                    result = result[0]
                elif len(result) == 0:
                    raise error.TestScriptError("Path returned an empty result!")
                else:
                    raise error.TestScriptError("More than one result!")

    return result

def save_fixtures(resources:list, fix_list:list[dict]) -> None:
    """
    Registers FHIR TestScript fixtures locally and, for those marked with
    ``autocreate``, uploads them to the FHIR server sequentially based on
    dependency order.

    Each static fixture is stored in the global ``FIXTURES`` list.  Fixtures whose
    ``autocreate`` flag is true are parsed for references, ordered by dependency,
    and created sequentially. References are replaced with server IDs as fixtures
    are created.

    :param resources: List of parsed JSON dicts or raw XML strings of the
        Example Instance files (one per fixture).
    :param fix_list: List of raw fixture definition dictionaries from the
        TestScript JSON (parallel to ``resources``).
    :raises Exception: If fixture creation fails.
    :raises error.CircularDependencyError: If fixtures have circular dependencies.
    :raises error.UnresolvedReferenceError: If autocreate fixtures have unresolved references.
    """
    global FIXTURES

    # Create all static fixture objects and parse references
    all_fixtures = []
    fixture_ids = []

    for res, fixture in zip(resources, fix_list):
        fix_id, fix_type = utils.extract_fhir_meta(res)
        fix_source_id = fixture.get("id")
        autocreate = fixture.get("autocreate", True)
        autodelete = fixture.get("autodelete", False)

        fixture_obj = Fixture(fix_id, fix_source_id,autocreate, autodelete, fix_type, res)
        all_fixtures.append(fixture_obj)
        if fix_id is not None:
            fixture_ids.append(fix_id)
        FIXTURES.append(fixture_obj)

    # Check for duplicate fixture IDs (from resource files)
    seen_ids = {}
    for fixture in all_fixtures:
        if fixture.fixture_id is None:
            continue
        if fixture.fixture_id in seen_ids:
            raise Exception(
                f"Fixture Ids need to be unique to correctly resolve references. "
                f"Duplicate ID '{fixture.fixture_id}' found in fixtures: "
                f"'{seen_ids[fixture.fixture_id].source_id}' and '{fixture.source_id}'"
            )
        seen_ids[fixture.fixture_id] = fixture

    # Parse references for each fixture
    for fixture in all_fixtures:
        fixture.references = reference_parser.parse_references(fixture.body, fixture_ids)
        log.debug("Fixture '%s': %s/%s (autocreate=%s, autodelete=%s, references=%s)",
                  fixture.source_id, fixture.type, fixture.fixture_id,
                  fixture.autocreate, fixture.autodelete, fixture.references or "none")

    autocreate_fixtures = [f for f in all_fixtures if f.autocreate]
    non_autocreate_fixtures = [f for f in all_fixtures if not f.autocreate]

    # If there are autocreate fixtures, resolve creation order and create them
    if autocreate_fixtures:
        try:
            ordered_fixtures = dependency_resolver.resolve_creation_order(autocreate_fixtures)
            log.debug("Fixture creation order: %s", ", ".join(f.source_id or "?" for f in ordered_fixtures))
            fixture_id_to_server_id = {}

            # Create static fixtures sequentially
            for fixture in ordered_fixtures:
                # Replace references with already-resolved server IDs
                resolved_body = dependency_resolver.replace_references(
                    fixture.body, fixture_id_to_server_id
                )
                fixture.body = resolved_body

                if isinstance(resolved_body, dict):
                    is_xml = False
                else:
                    is_xml = utils.string_type(resolved_body) == "xml"

                resource_type = fixture.type
                url = f"{FHIR_SERVER_BASE}/{resource_type}"
                log.info("Creating fixture '%s' (%s/%s)", fixture.source_id, resource_type, fixture.fixture_id)

                if is_xml:
                    headers = {"Content-Type": "application/fhir+xml", "Accept": "application/fhir+xml"}
                    request_id, response = comm_log.send_request("post", url, headers, resolved_body)
                else:
                    if isinstance(resolved_body, dict):
                        body_data = json.dumps(resolved_body, ensure_ascii=False)
                    elif isinstance(resolved_body, str):
                        body_data = resolved_body
                    else:
                        body_data = str(resolved_body)
                    headers = {"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"}
                    request_id, response = comm_log.send_request("post", url, headers, body_data)

                # Extract server ID from response
                if response.status_code >= 200 and response.status_code < 300:
                    location = response.headers.get("Location", "")
                    if location:
                        parts = location.rstrip("/").split("/")
                        if "_history" in parts:
                            history_idx = parts.index("_history")
                            server_id = parts[history_idx - 1]
                        else:
                            server_id = parts[-1]
                    else:
                        try:
                            if is_xml:
                                root = ET.fromstring(response.text)
                                ns = {'fhir': 'http://hl7.org/fhir'}
                                id_el = root.find('fhir:id', ns) if '}' in root.tag else root.find('id')
                                server_id = id_el.get('value', '') if id_el is not None else ''
                            else:
                                response_json = response.json()
                                server_id = response_json.get("id")
                        except Exception:
                            server_id = ""

                    if not server_id:
                        raise Exception(f"No ID found in response for fixture {fixture.fixture_id} ({request_id})")

                    # Update static fixture with server ID
                    fixture.server_id = server_id
                    fixture_id_to_server_id[fixture.fixture_id] = server_id
                    fixture.references_resolved = True
                    log.info("Fixture '%s' created as %s/%s", fixture.source_id, resource_type, server_id)
                else:
                    raise Exception(f"Failed to create fixture {fixture.fixture_id} ({request_id}): {response.status_code} - {response.text[:500]}")

            # Validate all references are resolved
            dependency_resolver.validate_all_references_resolved(autocreate_fixtures)

        except error.CircularDependencyError as e:
            raise
        except error.UnresolvedReferenceError as e:
            raise
        except Exception as e:
            raise

    # Mark non-autocreate fixtures as having no references to resolve (they're not created)
    for fixture in non_autocreate_fixtures:
        if not fixture.references:
            fixture.references_resolved = True
    
def save_profile(profilerefs : list, profile_ids : list[dict[str, str]]) -> None:
    """
    Stores FHIR StructureDefinition profile references in the global
    ``PROFILES`` dictionary, keyed by their TestScript-local ID.

    Supports both TestScript ``profile`` encodings:

    * **R5 ``canonical[]``** – ``profilerefs`` holds canonical URL strings and the
      element IDs are supplied out-of-band via the ``_profile`` primitive-extension
      array (``profile_ids``), paired positionally.
    * **R4 ``Reference``** – each entry in ``profilerefs`` is an object of the form
      ``{"id": ..., "reference": ...}`` and ``profile_ids`` is empty.

    :param profilerefs: List of profile entries – canonical URL strings (R5) or
        ``Reference`` objects (R4).
    :param profile_ids: List of ``_profile`` primitive-extension objects, each
        containing an ``id`` key (R5 only; empty for R4).
    """
    global PROFILES
    for idx, prof in enumerate(profilerefs):
        if isinstance(prof, dict):
            # R4 Reference form: {"id": ..., "reference": ...}
            pid = prof.get("id")
            if pid:
                PROFILES[pid] = prof.get("reference")
        else:
            # R5 canonical form: prof is a URL string; id comes from _profile[idx]
            pid = profile_ids[idx].get("id") if idx < len(profile_ids) and isinstance(profile_ids[idx], dict) else None
            if pid is None and isinstance(prof, str):
                profile_canonical = prof
                if profile_canonical.startswith("http"):
                    profile_canonical = profile_canonical
                    profile_canonical = profile_canonical[profile_canonical.rindex("/")+1:]
                    log.debug("Profile canonical ID extracted: %s", profile_canonical)
                else:
                    profile_canonical = None
            else:
                profile_canonical = None

            pid = profile_canonical if profile_canonical is not None else pid

            if pid:
                PROFILES[pid] = prof
    for pid, ref in PROFILES.items():
        log.debug("Profile '%s' -> %s", pid, ref)


def autodelete() -> None:
        """
        Deletes every fixture from the FHIR server whose ``autodelete`` flag
        is ``True`` and that was successfully created (i.e. has a non-empty
        ``server_id``).
        """
        global FIXTURES
        for fix in FIXTURES:
            if fix.autodelete and fix.server_id != "":
                log.info("Autodelete of fixture '%s' (%s/%s)", fix.source_id, fix.type, fix.server_id)
                request_id, response = comm_log.send_request("delete", f"{FHIR_SERVER_BASE}/{fix.type}/{fix.server_id}")
                if not response.ok:
                    log.warning("Autodelete of fixture '%s' returned HTTP %s [%s]",
                                fix.source_id, response.status_code, request_id)

def _error_cause(e: BaseException) -> str:
    """
    Returns the class name of the original exception behind ``e``, following
    the ``raise ... from`` chain (e.g. ``ConnectionError`` instead of the
    wrapping ``TestExecutionError``).
    """
    while e.__cause__ is not None:
        e = e.__cause__
    return type(e).__name__

def SETUP(setup_data : dict, fixture_list : list, resources) -> None:
    """
    Executes the **setup** phase of a FHIR TestScript.

    Creates static fixtures on the server (autocreate), rewrites inter-fixture
    references so they point to server-assigned IDs, and then runs every
    setup action in order.

    Setup assertions follow the same ``stopTestOnFail`` rules as in a test:
    with true the setup stops at once, otherwise the remaining setup actions
    still run.  Since the tests depend on the setup, any failed setup
    assertion aborts the TestScript afterwards.

    A failed assertion is recorded as ``fail``; a fixture or action that
    could not be executed is recorded as ``error``.

    :param setup_data: The ``setup`` dictionary from the TestScript JSON,
        or an empty dict when there is no explicit setup section.
    :param fixture_list: List of raw fixture definition dictionaries from
        the TestScript.
    :param resources: List of parsed JSON bodies of the Example Instance
        files that back the fixtures.
    :raises TestScriptError: If fixture creation, a setup operation or a
        setup assertion fails
    """
    global FIXTURES
    log.info("--- Setup")
    tracker = rt.get_result_tracker()
    tracker.start_outcome("Setup", "Setup")
    setup_actions = (setup_data or {}).get("action", []) or []
    declared_asserts = sum(1 for a in setup_actions if "assert" in a)
    tracker.set_assertion_count(declared_asserts)
    error_message = ""
    error_type = None
    failed = False
    warnings = []
    errors = []
    try:

        if fixture_list: #if there are static fixtures to save
            try:
                save_fixtures(resources, fixture_list)
            except Exception as e: #failure in autocreate
                error_type = _error_cause(e)
                error_message = f"Fixture initialization failed ({error_type}): {str(e)}"
                log.debug("Traceback:", exc_info=True)
                raise error.TestScriptError(error_message) from e

        for action in setup_data.get("action", []):
            try:
                execute_actions(action)
            except error.WarningException as we:
                warnings.append(f"⚠ WARNING: {str(we)}")
            except error.AssertionFailedContinueError as e:
                # stopTestOnFail false or missing - record and run the remaining setup actions
                failed = True
                errors.append(str(e))

        if errors:
            # the tests depend on the setup, so failed setup assertions abort the TestScript
            raise error.TestScriptError(f"Setup assertion failed: {'; '.join(errors)}")

    except error.TestScriptError:
        raise
    except AssertionError as ae: #stopTestOnFail true - stop the setup at once
        failed = True
        error_message = f"Setup stopped: {str(ae)}"
        raise error.TestScriptError(error_message) from ae
    except Exception as e: #action could not be executed
        error_type = _error_cause(e)
        error_message = f"Setup stopped ({error_type}): {str(e)}"
        raise error.TestScriptError(error_message) from e #stop the whole testscript
    finally:
        if failed:
            result, error_type = "fail", "AssertionError"
        elif error_message:
            result = "error"
        else:
            result = "pass"
        messages = errors + ([error_message] if error_message else [])
        if not messages:
            messages.append("Setup successful")
        messages.extend(warnings)
        tracker.finish_outcome(result=result, message=messages, error_type=error_type)

def TEST(test_data : dict) -> None:
    """
    Executes a single **test** phase of a FHIR TestScript.

    Iterates over all actions defined in the test.
    Assertion failures are recorded and the remaining actions still run,
    unless the assertion has ``stopTestOnFail`` set to true (raised as
    ``AssertionError``) or an action could not be executed
    (``TestExecutionError``); both stop the test, the next test still runs.

    The test is recorded as ``fail`` if any assertion failed, as ``error``
    if an action could not be executed, and as ``pass`` otherwise.

    :param test_data: A single ``test`` element dictionary from the
        TestScript JSON.
    """
    #Test Capabilities --> if Error --> skip test --> maybe in main

    test_name = test_data.get('name', 'Unnamed Test')
    failed = False
    error_message = ""
    error_type = None
    warnings = []
    errors = []
    log.info("--- Test '%s'", test_name)
    tracker = rt.get_result_tracker()
    tracker.start_outcome("Test", test_name)
    test_actions = (test_data or {}).get("action", []) or []
    declared_asserts = sum(1 for a in test_actions if "assert" in a)
    tracker.set_assertion_count(declared_asserts)

    try:
      
        for action in test_data.get("action" , []):
            try:
                execute_actions(action)

            #per action in test
            except error.WarningException as we:
                warnings.append(f"⚠ WARNING: {str(we)}")
            except error.AssertionFailedContinueError as e:
                failed = True
                errors.append(str(e))

    except AssertionError as e: #stopTestOnFail true
        failed = True
        error_message = str(e)
    except Exception as e: #action could not be executed
        error_type = _error_cause(e)
        error_message = f"Test stopped ({error_type}): {str(e)}"
        #test schould get stopped, and next test needs to start
    finally:
        if failed:
            result, error_type = "fail", "AssertionError"
        elif error_message:
            result = "error"
        else:
            result = "pass"
        messages = errors + ([error_message] if error_message else [])
        if not messages:
            messages.append("Test passed")
        messages.extend(warnings)
        tracker.finish_outcome(result=result, message=messages, error_type=error_type)
    
def TEARDOWN(teardown_data : dict) -> None:
    """
    Executes the **teardown** phase of a FHIR TestScript.

    Runs every teardown action (operations and assertions) and afterwards
    calls ``autodelete`` to remove all static fixtures whose ``autodelete`` flag
    is set.  ``autodelete`` also runs when a teardown action fails.

    Failures are recorded in the Teardown outcome and not raised, as there
    is nothing left to abort after the teardown.  A failed assertion is
    recorded as ``fail``; an action or autodelete that could not be executed
    as ``error``.

    :param teardown_data: The ``teardown`` dictionary from the TestScript
        JSON, or an empty dict when there is no explicit teardown section.
    """
    log.info("--- Teardown")
    tracker = rt.get_result_tracker()
    tracker.start_outcome("Teardown", "Teardown")
    teardown_actions = (teardown_data or {}).get("action", []) or []
    declared_asserts = sum(1 for a in teardown_actions if "assert" in a)
    tracker.set_assertion_count(declared_asserts)
    error_messages = []
    error_type = None
    failed = False
    warnings = []
    errors = []
    try:
        for action in teardown_data.get("action", []):
            try:
                execute_actions(action)
            except error.WarningException as we:
                warnings.append(f"⚠ WARNING: {str(we)}")
            except error.AssertionFailedContinueError as e:
                # stopTestOnFail false or missing - record and run the remaining teardown actions
                failed = True
                errors.append(str(e))

    except AssertionError as ae: #stopTestOnFail true - skip the remaining teardown actions
        failed = True
        errors.append(f"Teardown stopped: {str(ae)}")
    except Exception as e: #action could not be executed
        error_type = _error_cause(e)
        error_messages.append(f"Teardown stopped ({error_type}): {str(e)}")

    try:
        autodelete()
    except Exception as e:
        error_type = error_type or type(e).__name__
        error_messages.append(f"Autodelete of fixtures failed ({type(e).__name__}): {str(e)}")
        log.error("%s", error_messages[-1])
    finally:
        if failed:
            result, error_type = "fail", "AssertionError"
        elif error_messages:
            result = "error"
        else:
            result = "pass"
        messages = errors + error_messages
        if not messages:
            messages.append("Teardown successful")
        messages.extend(warnings)
        tracker.finish_outcome(result=result, message=messages, error_type=error_type)

def _record_abort(testscript: dict, message: str, error_type: str) -> None:
    """
    Records the abort of a TestScript in the result tracker.

    A phase (Setup/Test/Teardown) that fails records its own failing outcome
    before it raises.  An extra "Aborted" outcome (recorded as ``error``) is
    only added when nothing has recorded the failure yet, e.g. when the
    TestScript is invalid and no phase was started.  This way a single fault
    is counted only once.  The tests that did not run are recorded as skipped.

    :param testscript: The TestScript dictionary.
    :param message: Reason for the abort.
    :param error_type: Error classification for the outcome.
    """
    log.error("%s", message)
    trk = rt.get_result_tracker()
    ts_result = trk.current_testscript
    if trk.current_outcome:
        # A phase was interrupted before it could record its result
        trk.finish_outcome(result="error", message=[message], error_type=error_type)
    elif not ts_result or not ts_result.outcomes or ts_result.outcomes[-1].result not in ("fail", "error"):
        # Failed before any phase recorded the failure
        trk.start_outcome("Setup", "Aborted")
        trk.finish_outcome(result="error", message=[message], error_type=error_type)

    if ts_result:
        tests_run = sum(1 for o in ts_result.outcomes if o.class_type == "Test")
        for test in testscript.get("test", [])[tests_run:]:
            trk.start_outcome("Test", test.get('name', 'Unnamed Test'))
            trk.finish_outcome(result="skip", message=["Skipped: TestScript aborted"])

def test_fhir_operations(testscript_data : tuple[dict, list], testscript_path=""):
    """
    Main entry point that orchestrates a complete FHIR TestScript run.

    Extracts static fixtures, variables, and profiles from the TestScript, then
    drives execution through the three TestScript phases in order:
    **SETUP** → **TEST** → **TEARDOWN**.  On severe errors
    the run is aborted and ``autodelete`` is invoked to clean up
    server-side resources.  All global state (``FIXTURES``, ``REQ_RESP``,
    ``PROFILES``, ``VARIABLES``) is cleared at the end regardless of
    outcome.

    :param testscript_data: Tuple of ``(testscript_dict, resources_list)``
        as provided by ``load_testscript_data``.
    """

    global FHIR_SERVER_BASE
    FHIR_SERVER_BASE = conf_man.get_fhir_server() or ""

    if not conf_man.has_fhir_server():
        tracker = rt.get_result_tracker()
        ts_temp, _ = testscript_data
        nm = ts_temp.get('name', ts_temp.get('id', 'Unnamed TestScript'))
        log.warning("TestScript '%s' skipped: no FHIR server configured", nm)
        tracker.initialize_testscript(nm, ts_temp.get("url", testscript_path or ""))
        tracker.start_outcome("Setup", "Skipped")
        tracker.finish_outcome(result="skip", message=["No FHIR server configured"], error_type="Skipped")
        return

    testscript, resources = testscript_data

    tracker = rt.get_result_tracker()
    testscript_name = testscript.get('name', testscript.get('id', 'Unnamed TestScript'))
    tracker.initialize_testscript(testscript_name, testscript.get("url", testscript_path or ""))
    log.info("TestScript '%s' (%s)", testscript_name, testscript.get("url", "no url"))
    log.debug("%d fixture(s), %d variable(s), %d profile(s), %d test(s)",
              len(testscript.get("fixture", [])), len(testscript.get("variable", [])),
              len(testscript.get("profile", [])), len(testscript.get("test", [])))

    try:

        # Check for duplicate source IDs
        fixture_list = utils.get_fixture(testscript)
        validate.check_duplicate_source_ids(testscript, fixture_list)

        validate.validateTS(testscript) #see if the TestScript is valid

        variable_list = utils.get_variables(testscript)
        

        profile_list, prof_ids = utils.get_profile(testscript)
        # hier eine funktion die die jsonfiles von den profilen zurückgibt?
        if profile_list:
            save_profile(profile_list, prof_ids)

        if variable_list:
            save_variables(variable_list)

        SETUP(testscript.get("setup") or {}, fixture_list, resources) #there can only be one Setup
            
        for test in testscript.get("test", []):
            TEST(test)  

        TEARDOWN(testscript.get("teardown") or {}) #there can only be one Teardown

    except error.TestScriptError as tse:
        autodelete() #autodelete after everything went wrong
        _record_abort(testscript, f"TestScript aborted: {str(tse)}", _error_cause(tse))
    except Exception as e:
        log.debug("Traceback:", exc_info=True)
        _record_abort(testscript, f"Unexpected error ({type(e).__name__}): {str(e)}", _error_cause(e))
    finally:
        trk = rt.get_result_tracker()
        if trk.current_outcome:
            trk.finish_outcome(result="error", message=["Execution interrupted unexpectedly - phase did not complete"], error_type="Aborted")
        ts_result = trk.current_testscript
        if ts_result:
            level = logging.INFO if ts_result.outcome == "pass" else logging.WARNING if ts_result.outcome == "skip" else logging.ERROR
            log.log(level, "TestScript '%s' finished: %s (%.2f s)", ts_result.name, ts_result.outcome.upper(), ts_result.total_time)
            
        FIXTURES.clear() 
        REQ_RESP.clear()
        PROFILES.clear()
        VARIABLES.clear()
        
    