import json
import subprocess
import os
from typing import Any
from fhirpathpy import evaluate
from lxml import etree
from jsonpath_ng import parse
from impl.test_script_evaluator.test_script_evaluator_log_to_file import log_to_file, parse_fhir_header
from impl.model.interaction import Interaction
from impl.test_script_evaluator.utils import get_full_path
from typing import Literal, Any
from lxml import etree


""" 
make small validations
DO NOT DO WHOLE ASSERTIONS

--> split validate_response up

--> add one for every assert??
"""

operator_type = Literal['equals', 'notEquals', 'in', 'notIn', 'greaterThan', 'lessThan', 'empty', 'notEmpty', 'contains', 'notContains', 'eval', 'manualEval']


def validate_operator(operator : operator_type, valueResp: Any, valueTS:Any) -> None:
    
    match operator:
        case "equals":
            valueTS = list_val(valueTS)
            valueResp = list_val(valueResp)
            assert valueResp == valueTS 

        case "notEquals":
            valueTS = list_val(valueTS)
            valueResp = list_val(valueResp)
            assert valueResp != valueTS

        case "in":
            assert valueResp in valueTS

        case "notIn":
            assert valueResp not in valueTS 

        case "greaterThan":
            valueTS = list_val(valueTS)
            valueResp = list_val(valueResp)
            assert valueResp > valueTS

        case "lessThan":
            valueTS = list_val(valueTS)
            valueResp = list_val(valueResp)
            assert valueResp < valueTS

        case "empty":
            assert not valueResp #not only is none?

        case "notEmpty":
            assert valueResp 

        case "contains":
            assert isinstance(valueResp, str), "contains Operator is only valid with a string"
            assert isinstance(valueTS, str), "contains Operator is only valid with a string"
            assert valueTS in valueResp

        case "notContains":
            assert isinstance(valueResp, str), "notContains Operator is only valid with a string"
            assert isinstance(valueTS, str), "notContains Operator is only valid with a string"
            assert valueTS not in valueResp
        case "eval":
            assert isinstance(valueResp, bool), "evaluation result is not a boolean"
            assert valueResp

def list_val(value) -> Any:
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        else:
            TypeError("value to compare is not the Same type")
    else:
        return value
    
def validate_content_type(response : Interaction, expected_type, operator: operator_type) -> None:
    """
    Validates whether the server response matches the expected content type.
    If no expected_type is specified, no validation is performed.
    :param response: The HTTP response object returned by the server.
    :param expected_type:  The expected Content-Type (e.g., "json", "xml", or a full MIME type).
                           If None or empty, no validation is performed.
    :return: None
    """

    actual_content_type = response.header.get("Content-Type", "")
    expected_type = parse_fhir_header(expected_type)

    log_to_file(f"Asserting Content-Type {actual_content_type} {operator} {expected_type}'")
    validate_operator(operator, actual_content_type, expected_type)


def validate_responseCode(response: Interaction, expected_codes, operator: operator_type) -> None:
    status_code = str(response.status_code)
    log_to_file(f"Asserting response code {status_code} {operator} {expected_codes}")
    validate_operator(operator, status_code, expected_codes)

def validate_response(response: Interaction, expected, operator: operator_type) -> None:
    if not response.reason:
        raise AssertionError("No response-reason found!")
    log_to_file(f"Asserting response {response.reason} {operator} {expected}")
    validate_operator(operator, response.reason, expected)
    
def execute_validator(cmd : str) -> list[str]:
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
    validator = get_full_path("test_script_evaluator/validator_cli.jar")
    path = get_full_path("temp/temp.json")
    ts_string = json.dumps(testScript)

    os.makedirs(get_full_path("temp"), exist_ok=True)
    with open(path, "w") as f:
        f.write(ts_string)

    cmd = f"java -jar {validator} {path} -tx n/a"
    output = execute_validator(cmd)
    os.remove(path)
    os.rmdir(get_full_path("temp"))

    try: 
        check_result(output)
    except AssertionError as ae:
        raise Exception("TestScript not valid: " + str(ae))


def validate_profile_assertion(profileRef: str, response: Interaction) -> str:
    log_to_file(f"Asserting profile {profileRef}")

    prof_folder = get_full_path("Profiles")
    resource = get_full_path("temp/temp.json")
    validator = get_full_path("test_script_evaluator/validator_cli.jar")

    os.makedirs(get_full_path("temp"), exist_ok=True)
    with open(resource, "w") as f:
        f.write(response.body)

    cmd = f"java -jar {validator} -ig {prof_folder} {resource} -profile {profileRef} -tx n/a"
    output = execute_validator(cmd)
    os.remove(resource)
    os.rmdir(get_full_path("temp"))

    return check_result(output)

def check_result(output: list[str]) -> str:

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

    return warnings + "\n" + information #if no warnings and no error

def eval_compareTo(fixture, assertion : dict[str,Any]):
    if "compareToSourceExpression" in assertion:
        return do_expression(fixture.body, assertion.get("compareToSourceExpression"))
    elif "compareToSourcePath" in assertion:
        return doPath(fixture.body, assertion.get("compareToSourcePath"))


def do_expression(body, expression : str):
    #maybe check if something comes from this --> if not invalid ?
    return evaluate(body, expression)

def doPath(body, path:str):

    """
    Check  if body is xml or json
    Check if path is xpath or jsonpath
    
    --> different ways to evaluate
    --> do I want to convert to json or xml?
    """
    type = "xml"
    result = None

    print("temporary bridging until path issue is resolved")

    #check if xml or jsonpath
    if path == "xml":
        result = xmlPath(str(body), path)
    elif path == "json":
        result = jsonPath(body, path)


    #print("not yet supported")
    return result

def xmlPath(body : str, path:str): #get xml as str?
    root = etree.fromstring(body)
    ns = {'fhir': 'http://hl7.org/fhir'} #change to dynamically get namespace of xml?

    # Alle Family-Namen
    result = root.xpath(f"//{path}", namespaces=ns)
    for res in result:
        if not isinstance(res, str):
            raise ValueError(f"Path {path} could not be evaluated")
    print(result)
    return result

def jsonPath(body : str, path:str):
    if isinstance(body,str):
        body = json.loads(body)

    jsonpath_expr = parse(path)
    return ([match.value for match in jsonpath_expr.find(body)])
    

