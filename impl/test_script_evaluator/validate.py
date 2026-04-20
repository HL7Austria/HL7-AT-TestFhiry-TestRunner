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



""" 
make small validations
DO NOT DO WHOLE ASSERTIONS

--> split validate_response up

--> add one for every assert??
"""



def validate_content_type(response, expected_type=None):
    """
    Validates whether the server response matches the expected content type.
    If no expected_type is specified, no validation is performed.
    :param response: The HTTP response object returned by the server.
    :param expected_type:  The expected Content-Type (e.g., "json", "xml", or a full MIME type).
                           If None or empty, no validation is performed.
    :return: None
    """

    # If no expected type is specified, skip
    if not expected_type:
        log_to_file("Skipping Content-Type validation (no expected type provided).")
        return

    actual_content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
    expected_type = parse_fhir_header(expected_type)

    log_to_file(f"Checking Content-Type: expected '{expected_type}', got '{actual_content_type}'")

    are_equal = actual_content_type == expected_type  # Python does not create a diff because it does not directly see 'string == string'
    assert are_equal, f"Content-Type mismatch: got '{actual_content_type}', expected '{expected_type}'"


def validate_response(assertion, response):
    """
    Validates HTTP response against assertion rules.

    Checks if response status code matches expected codes from assertion.

    :param assertion: Dictionary containing validation rules with 'responseCode' key.
    :param response: The HTTP response object returned by the server.
    :return: None
    """

    if "responseCode" in assertion:
        expected_codes = [code.strip() for code in assertion.get("responseCode", "").split(",")]
        status_code = str(response.status_code)
        log_to_file(f"Asserting response code {status_code} in {expected_codes}")
        #operator = assertion.get("operator")
        assert status_code in expected_codes, f"Assertion failed: {status_code} not in {expected_codes}"

def execute_validator(cmd):
    popen = subprocess.Popen(cmd,stdout=subprocess.PIPE, shell=True)

    if popen.stdout is None:
        raise ValueError("Something went wrong with the subprocess")
    
    raw = popen.stdout.read()
    popen.stdout.close()
    popen.wait()

    decoded = raw.decode("utf-8")
    output = decoded.splitlines(keepends=True)

    return output

def validateTS(testScript: dict[str, Any]):
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
    result = root.xpath(f"/{path}", namespaces=ns)
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
    

