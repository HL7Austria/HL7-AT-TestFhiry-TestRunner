import json
import re
from typing import Any, List, Union
from jsonpath_ng import parse as jsonpath_parse
from lxml import etree
from fhirpathpy import evaluate
from impl.test_script_evaluator.test_script_evaluator_log_to_file import log_to_file, parse_fhir_header



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

def doPath(body: str, path: str,
           force_body_type: str = None,
           force_path_type: str = None,
           xpath_as_text: bool = True) -> Union[bool, List[Any]]:

    body_type = force_body_type or detect_body_type(body)
    path_type = force_path_type or detect_path_type(path)

    if body_type == 'json' and path_type == 'jsonpath':
        return evaluate_jsonpath(body, path)

    if body_type == 'xml' and path_type == 'xpath':
        return evaluate_xpath(body, path, as_text=xpath_as_text)

    raise ValueError(
        f"Cannot evaluate: body_type={body_type}, path_type={path_type}. "
        f"body starts with: {body.strip()[:20]!r}, path: {path!r}"
    )


def detect_body_type(body: str) -> str:
    """
    Return 'json', 'xml', or 'unknown' based on the body string.
    """
    if body is None:
        return 'unknown'

    s = body.strip()
    if not s:
        return 'unknown'

    # Very simple heuristics; adjust if you have special cases
    if s.startswith('{') or s.startswith('['):
        return 'json'
    if s.startswith('<'):
        return 'xml'
    return 'unknown'


def detect_path_type(path: str) -> str:
    """
    Return 'jsonpath', 'xpath', or 'unknown'.
    """
    path = path.strip()

    # Very strong JSONPath indicators
    if path.startswith('$'):
        return 'jsonpath'
    if path.startswith('@.'):
        return 'jsonpath'

    # Strong XPath indicators
    if path.startswith('/') or path.startswith('//') or path.startswith('.//'):
        return 'xpath'
    if path.startswith('.'):
        return 'xpath'
    if path.startswith('@'):
        return 'xpath'

    # Heuristics:
    if re.search(r'\$\b|\$\[|@\.', path):
        return 'jsonpath'

    if re.search(r'//|/@|text\(\)|\bcontains\(', path):
        return 'xpath'

    # If it has '/' but no '$', assume XPath
    if '/' in path and '$' not in path:
        return 'xpath'

    return 'unknown'


def evaluate_jsonpath(body: str, path: str) -> List[Any]:
    data = json.loads(body)
    expr = jsonpath_parse(path)
    return [m.value for m in expr.find(data)]


def evaluate_xpath(body: str, path: str,
                   as_text: bool = False) -> Union[bool, List[Any]]:
    root = etree.fromstring(body.encode("utf-8"))
    result = root.xpath(path)

    # lxml returns a plain bool for boolean XPath expressions
    if isinstance(result, bool):
        return result

    # Non-boolean result: normalize to list
    if not isinstance(result, list):
        result = [result]

    if not as_text:
        return result

    out: List[Any] = []
    for r in result:
        if isinstance(r, etree._Element):
            out.append("".join(r.itertext()))
        else:
            out.append(str(r))
    return out
 
