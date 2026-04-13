import json
from jsonpath_ng import parse, jsonpath
from fhirpathpy import evaluate
import json
from jsonpath_ng import parse, jsonpath
from fhirpathpy import evaluate
from impl.test_script_evaluator.test_script_evaluator_log_to_file import log_to_file, parse_fhir_header
from fhirpathpy import evaluate
from lxml import etree
from impl.model.interaction import Interaction


""" 
make small validations
DO NOT DO WHOLE ASSERTIONS

--> split validate_response up

--> add one for every assert??
"""


def validate_operator(operator, valueResp, valueTS):
    #	equals | notEquals | in | notIn | greaterThan | lessThan | empty | notEmpty | contains | notContains | eval | manualEval

    #https://hl7.org/fhir/testing.html#assertion-table

    
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
            assert valueResp is None

        case "notEmpty":
            assert valueResp 

        case "contains":
            assert isinstance(valueResp, str)
            assert isinstance(valueTS, str)
            assert valueTS in valueResp

        case "notContains":
            assert isinstance(valueResp, str)
            assert isinstance(valueTS, str)
            assert valueTS not in valueResp
        case "eval":
            assert isinstance(valueResp, bool), "evaluation result is not a boolean"
            assert valueResp

def list_val(value):
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        else:
            TypeError("value to compare is not the Same type")
    else:
        return value
    

def validate_content_type(response, expected_type, operator):
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

    log_to_file(f"Asserting Content-Type: expected '{expected_type}', got '{actual_content_type}'")
    validate_operator(operator, actual_content_type, expected_type)


def validate_responseCode(response, expected_codes, operator):
    status_code = str(response.status_code)
    log_to_file(f"Asserting response code {status_code} {operator} {expected_codes}")
    validate_operator(operator, status_code, expected_codes)

def validate_response(response, expected, operator):
    log_to_file(f"Asserting response {response} {operator} {expected}")
    validate_operator(operator, response, expected)



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
    




