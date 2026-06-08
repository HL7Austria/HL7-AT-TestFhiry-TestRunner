import json
import re
import subprocess
import os
from pathlib import Path
from fhirpathpy import evaluate
from jsonpath_ng import parse
from impl.model.interaction import Interaction
from typing import Literal, Any
from lxml import etree
import impl.test_script_evaluator.utils as utils
import importlib
import xml.etree.ElementTree as ET
import xmltodict
import impl.test_script_evaluator.configuration_manager as conf_man
import impl.exception.Error as error

operator_type = Literal['equals', 'notEquals', 'in', 'notIn', 'greaterThan', 'lessThan', 'empty', 'notEmpty', 'contains', 'notContains', 'eval', 'manualEval']


def convert_xml_to_json(xml_string: str) -> dict:
    """Konvertiert FHIR XML zu JSON Dictionary - funktioniert für jeden Resource-Typ"""
    # Resource-Typ aus XML extrahieren
    root = ET.fromstring(xml_string)
    resource_type = root.tag.split('}')[-1] if '}' in root.tag else root.tag
    
    # Dynamisch die entsprechenden Resource-Klasse importieren
    try:
        module = importlib.import_module(f"fhir.resources.{resource_type.lower()}")
        resource_class = getattr(module, resource_type)
        # XML parsen und zu JSON konvertieren (bytes für XML-Deklaration)
        model = resource_class.model_validate_xml(xml_string.encode('utf-8'))
        return model.model_dump()
    except (ImportError, AttributeError):
        # Fallback: xmltodict für robuste XML-zu-JSON-Konvertierung
        return xmltodict.parse(xml_string)


def validate_operator(operator : operator_type, valueResp: Any, valueTS:Any) -> None:
    """Applies a FHIR TestScript comparison operator to two values.

    :param operator: The comparison operator name as defined in the
        FHIR TestScript specification.
    :param valueResp: The actual value obtained from the server response.
    :param valueTS: The expected value defined in the TestScript assertion.
    :raises AssertionError: If the comparison does not hold.
    """
    match operator:
        case "equals":
            valueTS = list_val(valueTS)
            valueResp = list_val(valueResp)
            assert valueResp == valueTS, f"Expected '{valueTS}', got '{valueResp}'"

        case "notEquals":
            valueTS = list_val(valueTS)
            valueResp = list_val(valueResp)
            assert valueResp != valueTS, f"Expected value different from '{valueTS}', got '{valueResp}'"

        case "in":
            assert valueResp in valueTS, f"Expected '{valueResp}' to be in '{valueTS}'"

        case "notIn":
            assert valueResp not in valueTS, f"Expected '{valueResp}' to not be in '{valueTS}'"

        case "greaterThan":
            valueTS = list_val(valueTS)
            valueResp = list_val(valueResp)
            assert valueResp > valueTS, f"Expected '{valueResp}' to be greater than '{valueTS}'"

        case "lessThan":
            valueTS = list_val(valueTS)
            valueResp = list_val(valueResp)
            assert valueResp < valueTS, f"Expected '{valueResp}' to be less than '{valueTS}'"

        case "empty":
            assert not valueResp, f"Expected empty value, got '{valueResp}'" #not only is none?

        case "notEmpty":
            assert valueResp, f"Expected non-empty value, got '{valueResp}'"

        case "contains":
            assert isinstance(valueResp, str), "contains Operator is only valid with a string"
            assert isinstance(valueTS, str), "contains Operator is only valid with a string"
            assert valueTS in valueResp, f"Expected '{valueResp}' to contain '{valueTS}'"

        case "notContains":
            assert isinstance(valueResp, str), "notContains Operator is only valid with a string"
            assert isinstance(valueTS, str), "notContains Operator is only valid with a string"
            assert valueTS not in valueResp, f"Expected '{valueResp}' to not contain '{valueTS}'"

        case "eval":
            assert isinstance(valueResp, bool), "evaluation result is not a boolean"
            assert valueResp, f"Expected evaluation result to be True, got '{valueResp}'"

def list_val(value) -> Any:
    """Unwraps a single-element list to its contained value.

    :param value: A value that may or may not be a list.
    :returns: The unwrapped scalar if the input is a single-element list,
        or the original value unchanged.
    :raises TypeError: If the input is a list with more than one element.
    """
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        else:
            raise TypeError("value to compare is not the Same type")
    else:
        return value
    
def validate_content_type(response : Interaction, expected_type, operator: operator_type) -> None:
    """Validates the Content-Type header of a server respons
    
    :param response: The ``Interaction`` containing the server response headers.
    :param expected_type: The expected Content-Type value (short form or full MIME type).
    :param operator: The comparison operator to apply.
    :raises AssertionError: If the Content-Type does not satisfy the operator check.
    """

    actual_content_type = response.header.get("Content-Type", "")
    
    utils.log_to_file(f"Asserting Content-Type {actual_content_type} {operator} {expected_type}'")
    validate_operator(operator, actual_content_type, expected_type)

def validate_expression(fixture, expression : str, operator: operator_type, value = None) ->None:
    
    if isinstance(fixture.body, str):
        if utils.string_type(fixture.body) == "json":
            body_use = json.loads(fixture.body)
        elif utils.string_type(fixture.body) == "xml":
            # XML zu JSON konvertieren für FHIRPath
            body_use = convert_xml_to_json(fixture.body)
        else:
            raise Exception ("fhirpath does not function if response is not json or xml")
    else:
        body_use = fixture.body

    res = eval_expression(body_use, expression)

    if isinstance(res, list):
        if len(res) == 1:
            res = res[0]
    if isinstance(value, list):
        if len(value) == 1:
            value = value[0]
    utils.log_to_file(f"Asserting Expression {expression}: {res} {operator} {value}")
    validate_operator(operator, res, value)

def validate_responseCode(response: Interaction, expected_codes, operator: operator_type) -> None:
    """Validates the HTTP status code of a server response.

    :param response: The ``Interaction`` containing the server response.
    :param expected_codes: List of expected status code strings.
    :param operator: The comparison operator to apply.
    :raises AssertionError: If the status code does not satisfy the operator check.
    """
    status_code = str(response.status_code)
    utils.log_to_file(f"Asserting response code {status_code} {operator} {expected_codes}")
    validate_operator(operator, status_code, expected_codes)

RESPONSE_CODE_MAP = {
    "okay": "200",
    "created": "201",
    "noContent": "204",
    "notModified": "304",
    "bad": "400",
    "forbidden": "403",
    "notFound": "404",
    "methodNotAllowed": "405",
    "conflict": "409",
    "gone": "410",
    "preconditionFailed": "412",
    "unprocessable": "422",
}

def validate_response(response: Interaction, expected, operator: operator_type) -> None:
    """Validates the HTTP status code of a server response using the FHIR
    ``assert.response`` code as a shorthand for ``assert.responseCode``.

    Maps the FHIR response display code (e.g. ``'okay'``, ``'created'``) to
    the corresponding HTTP status code and compares it against the actual
    status code of the response.

    :param response: The ``Interaction`` containing the server response.
    :param expected: The expected FHIR response display code from the TestScript.
    :param operator: The comparison operator to apply.
    :raises AssertionError: If the status code does not satisfy the operator check.
    :raises TestScriptError: If the expected response code is not a recognized
        FHIR AssertionResponseTypes value.
    """
    expected_status = RESPONSE_CODE_MAP.get(expected)
    if not expected_status:
        raise error.TestScriptError(f"Unknown response code '{expected}'. Must be one of: {', '.join(RESPONSE_CODE_MAP.keys())}")
    actual_status = str(response.status_code)
    utils.log_to_file(f"Asserting response {actual_status} {operator} {expected} (mapped to {expected_status})")
    validate_operator(operator, actual_status, expected_status)
    
def execute_validator(cmd : str) -> list[str]:
    """Runs a shell command and returns its stdout as a list of lines.

    Used to invoke the FHIR HL7 Validator CLI JAR.

    :param cmd: The full command-line string to execute.
    :returns: List of output lines (with line endings preserved).
    :raises ValueError: If the subprocess stdout pipe could not be opened.
    """
    popen = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)

    if popen.stdout is None:
        raise ValueError("Something went wrong with the subprocess")
    
    raw = popen.stdout.read()
    popen.stdout.close()
    popen.wait()

    decoded = raw.decode("utf-8")
    output = decoded.splitlines(keepends=True)

    return output

def validateTS(testScript: dict[str, Any]) -> None:
    """Validates a FHIR TestScript resource using the HL7 Validator CLI.

    Serialises the TestScript to a temporary JSON file, runs the validator,
    and removes the temp file afterwards.

    :param testScript: Parsed TestScript JSON dictionary.
    :raises Exception: If the validator reports errors (wraps the
        ``AssertionError`` from ``check_result``).
    """
    base_path = Path(conf_man.get_config_manager().path)
    validator = base_path / "validator_cli.jar"
    temp_dir = base_path / "temp"
    path = temp_dir / "temp.json"
    ts_string = json.dumps(testScript)

    os.makedirs(temp_dir, exist_ok=True)
    with open(path, "w") as f:
        f.write(ts_string)

    cmd = f"java -jar {validator} {path} -tx n/a"
    output = execute_validator(cmd)
    os.remove(path)
    os.rmdir(temp_dir)

    try: 
        check_result(output)
    except AssertionError as ae:
        raise Exception("TestScript not valid: " + str(ae))

def validate_profile_assertion(profileRef: str, response: Interaction) -> str:
    """Validates a server response body against a FHIR StructureDefinition profile.

    Writes the response body to a temporary file, invokes the HL7 Validator
    CLI with the profile reference and the local Profiles folder as an
    implementation guide, and removes the temp file afterwards.

    :param profileRef: The canonical URL of the profile to validate against.
    :param response: The ``Interaction`` whose body will be validated.
    :returns: A string containing any warnings and information messages from
        the validator (empty if none).
    :raises AssertionError: If the validator reports errors.
    """
    utils.log_to_file(f"Asserting profile {profileRef}")

    base_path = Path(conf_man.get_config_manager().path)
    temp_dir = base_path / "temp"
    pathF = temp_dir / "temp"
    if utils.string_type(response.body) == "json":
        pathF = Path(str(pathF) + ".json")
    elif utils.string_type(response.body) == "xml":
        pathF = Path(str(pathF) + ".xml")
    else:
        raise TypeError("Response body in unexpected format!")

    prof_folder = base_path / "Profiles"
    resource = pathF
    validator = base_path / "validator_cli.jar"

    os.makedirs(temp_dir, exist_ok=True)
    with open(resource, "w") as f:
        f.write(response.body)

    cmd = f"java -jar {validator} -ig {prof_folder} {resource} -profile {profileRef} -tx n/a"
    output = execute_validator(cmd)
    os.remove(resource)
    os.rmdir(temp_dir)

    return check_result(output)

def check_result(output: list[str]) -> str:
    """Parses HL7 Validator CLI output and raises on errors.

    Scans the output lines for the summary section (starting at ``*:``) and
    collects error, warning, and information lines.

    :param output: List of stdout lines from the validator process.
    :returns: A string of warnings and information messages.
    :raises AssertionError: If any error lines are found in the output.
    """

    errors = ""
    warnings = ""
    information = ""
    start = False

    for line in output:
        if "*:" in line: #start getting errors after the Summary-start of the validator
            start = True
        if start:
            if "Error" in line:
                errors += "\n" + line
            if "Warning" in line:
                warnings += "\n" + line
            if "Information" in line: #weis nicht obs sowas wirklich gibt
                information += "\n" + line
    if(errors != ""):
        raise AssertionError("Profile Assertion failed!\n" + errors + "\n" + warnings + "\n" + information)

    return warnings + "\n" + information #if no error

def eval_compareTo(fixture, assertion : dict[str,Any]):
    """Evaluates the comparison value from a ``compareToSourceId`` assertion.

    Extracts the value from the referenced fixture using either
    ``compareToSourceExpression`` or ``compareToSourcePath``.

    :param fixture: The ``Fixture`` or ``Interaction`` referenced by
        ``compareToSourceId``.
    :param assertion: The assertion dictionary containing the comparison
        field (``compareToSourceExpression`` or ``compareToSourcePath``).
    :returns: The evaluated comparison value.
    """
    if "compareToSourceExpression" in assertion:
        if isinstance(fixture.body, str):
            if utils.string_type(fixture.body) == "json":
                body_use = json.loads(fixture.body)
            elif utils.string_type(fixture.body) == "xml":
                # XML zu JSON konvertieren für FHIRPath
                body_use = convert_xml_to_json(fixture.body)
            else:
                raise Exception ("fhirpath does not function if response is not json or xml")
        else:
            body_use = fixture.body

        return eval_expression(body_use, assertion.get("compareToSourceExpression"))
    elif "compareToSourcePath" in assertion:
        return eval_path(fixture.body, assertion.get("compareToSourcePath"))


def eval_expression(body : dict[str, Any], expression : str):
    """Evaluates a FHIRPath expression against a resource body.

    :param body: The FHIR resource (dict or JSON string) to evaluate against.
    :param expression: A FHIRPath expression string.
    :returns: The evaluation result from the FHIRPath engine.
    """
    #maybe check if something comes from this --> if not invalid ?
    return evaluate(body, expression)

def validate_path(response: Interaction, path:str, expected, operator: operator_type) -> None:
    
    """Validates the Path from an Assertion.
    The Path-type is checked so it matches with the Content-Type.

    :param response: The ``Interaction`` containing the server response.
    :param path: XPath or JsonPath of the Assertion.
    :param expected: the expected value for the comparison.
    :param operator: The comparison operator to apply.
    :raises AssertionError: If the path-result does not satisfy the operator check.
    """
    path_type = utils.detect_path_type(path)
    if response.header.get("Content-Type"):
        if not path_type in response.header.get("Content-Type"): #check if pathtype is the same as content-type
            raise AssertionError(f"Response-Body is not of type {path_type}!")

    if not response.body:
        raise AssertionError("Response-Body is empty and cannot be tested with path.")
    res = eval_path(response.body, path)
    utils.log_to_file(f"Asserting Path: {path}, {res} {operator} {expected}.")
    validate_operator(operator, res, expected)

def validate_headerfield(response: Interaction, field:str, expected: Any, operator: operator_type) -> None:
    if not response.header:
        raise AssertionError("Response has no saved Headers!")
    validate_operator(operator, response.header.get(field), expected)

def eval_path(body, path:str):
    """Evaluates an XPath or JSONPath expression against a resource body.

    Determines the path type (``'xml'`` or ``'json'``) and delegates to
    ``xmlPath`` or ``jsonPath`` accordingly.

    :param body: The FHIR resource body (dict, JSON string, or XML string).
    :param path: The path expression string (XPath or JSONPath).
    :returns: The evaluation result, or ``None`` if the path type could not
        be determined.
    """
    body_type = ""
    if isinstance(body, dict):
        body_type = "json"
    else:
        body_type = utils.string_type(body)

    result = None
    path_type = utils.detect_path_type(path)
    if body_type != path_type : 
        raise Exception(f"Path {path} is not compatible with body type {body_type}!")

    #check if xml or jsonpath
    if path_type == "xml":
        result = eval_xpath(str(body), path)
    elif path_type == "json":
        result = eval_json_path(body, path)
    else:
        raise Exception(f"Path {path} could not be identified as XPath or JsonPath!")

    return result

def eval_xpath(body : str, path:str):
    """
    Evaluates an XPath expression against an XML resource body.
    If a namespace exists but no prefix in path it uses that ns as prefix.

    :param body: The XML resource as a string.
    :param path: The XPath expression to evaluate.
    :returns: List of matching string values.
    :raises ValueError: If any match result is not a string.
    """
    body_cleaned = body
    if isinstance(body, str):
        body_cleaned = re.sub(r'<\?xml[^?]*\?>', '', body, count=1).encode('utf-8')
        #remove so that lxml doesn't have a problem with the encoding string
    root = etree.fromstring(body_cleaned)
    for elem in root.iter(): #removing namespaces... do I want that?
        elem.tag = etree.QName(elem).localname
        for attr_name in list(elem.attrib):
            local = etree.QName(attr_name).localname
            if local != attr_name:
                elem.attrib[local] = elem.attrib.pop(attr_name)
    etree.cleanup_namespaces(root)

    result = root.xpath(path)
    return result

def eval_json_path(body : str, path:str):
    """Evaluates a JSONPath expression against a JSON resource body.

    :param body: The FHIR resource as a dict or JSON string.
    :param path: The JSONPath expression to evaluate.
    :returns: List of matched values.
    """
    if isinstance(body,str):
        body = json.loads(body)

    jsonpath_expr = parse(path)
    return ([match.value for match in jsonpath_expr.find(body)])

def check_duplicate_source_ids(testscript: dict[str, Any], fixture_list: list[dict]) -> None:
    """Checks for duplicate source IDs in a TestScript.

    Collects all fixture IDs, response IDs, and request IDs from operations
    and raises an error if any duplicates are found.

    :param testscript: Parsed TestScript JSON dictionary.
    :param fixture_list: List of raw fixture definition dictionaries from the TestScript.
    :raises Exception: If duplicate source IDs are found.
    """
    source_ids = []

    # Collect fixture IDs
    for fixture in fixture_list:
        fixture_id = fixture.get("id")
        if fixture_id:
            source_ids.append(("fixture", fixture_id))

    # Collect responseId and requestId from operations in setup, test, and teardown
    phases = ["setup", "test", "teardown"]
    for phase in phases:
        if phase == "test":
            phase_data = testscript.get(phase, [])
            if not isinstance(phase_data, list):
                phase_data = [phase_data] if phase_data else []
        else:
            phase_data = testscript.get(phase, {})
            if not isinstance(phase_data, dict):
                phase_data = {}

        # Handle test phase (list of test objects)
        if phase == "test":
            for test_obj in phase_data:
                actions = test_obj.get("action", []) if isinstance(test_obj, dict) else []
                for action in actions:
                    if "operation" in action:
                        op = action["operation"]
                        response_id = op.get("responseId")
                        request_id = op.get("requestId")
                        if response_id:
                            source_ids.append(("responseId", response_id))
                        if request_id:
                            source_ids.append(("requestId", request_id))
        else:
            # Handle setup and teardown phases (single object with actions)
            actions = phase_data.get("action", []) if isinstance(phase_data, dict) else []
            for action in actions:
                if "operation" in action:
                    op = action["operation"]
                    response_id = op.get("responseId")
                    request_id = op.get("requestId")
                    if response_id:
                        source_ids.append(("responseId", response_id))
                    if request_id:
                        source_ids.append(("requestId", request_id))

    # Check for duplicates
    seen_ids = {}
    for id_type, id_value in source_ids:
        if id_value in seen_ids:
            raise Exception(f"Duplicate source ID found: '{id_value}' used in both {seen_ids[id_value]} and {id_type}. TestScript will be skipped.")
        seen_ids[id_value] = id_type
    
