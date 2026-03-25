import json
from jsonpath_ng import parse, jsonpath
from fhirpathpy import evaluate
from impl.test_script_evaluator.test_script_evaluator_log_to_file import log_to_file, parse_fhir_header
from fhirpathpy import evaluate
from lxml import etree



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
    




