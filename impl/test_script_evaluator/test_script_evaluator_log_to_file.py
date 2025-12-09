import json
import requests
import pytest
from pathlib import Path
import os
from datetime import datetime
from impl.Transactions.transactions import *
from impl.exception.TestExecutionError import TestExecutionError
from profile_manager import ProfileManager
from validate import *

FHIR_SERVER_BASE = "http://cql-sandbox.projekte.fh-hagenberg.at:8080/fhir"
saved_resource_id = ""
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"test_results_{timestamp}.txt"

BASE_DIR = Path(__file__).resolve().parent.parent

profile_manager = ProfileManager()
profile_manager.make_profile_list(str(BASE_DIR) + "/Profiles")  # Path to profile

RESULTS_DIR = BASE_DIR / "Results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE_PATH = RESULTS_DIR / log_filename
LOG_FILE_PATH = os.path.abspath(LOG_FILE_PATH)

# Init logfile
with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(f"FHIR Test Log - {datetime.now()}\n\n")


def log_to_file(message):
    """
    Logs a message to both console and log file.
    :param message: The message to log.
    """
    print(message)
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(message + "\n")


# Help function for loading JSON files
def load_json(path):
    """
    Loads a JSON File from the given path.
    :param path: The path to the JSON file.
    :return: Parsed JSON content as dictionary.
    """
    full_path = BASE_DIR / path
    printInfoJson(path)
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)


def printInfoJson(path):
    """
    Logs information about loaded JSON files based on their path.

    :param path: Path of the loaded file.
    """
    if "Test_Scripts" in str(path):
        filename = os.path.basename(path)
        name_without_extension = os.path.splitext(filename)[0]
        log_to_file(f"\n\n=========== Starting Testscript: {name_without_extension} ===========")
    if "Example_Instances" in str(path):
        log_to_file(f"Load Example Instance: {path}")
    if "Profiles" in str(path):
        log_to_file(f"Load Profile: {path}")


def parse_fhir_header(value):
    """
    Maps short forms like 'json' or 'xml' to FHIR-compliant MIME types.

    :param value: The header value to parse.
    :return: Full MIME type string.
    """
    if not value:
        return "application/fhir+json"
    value = value.lower()
    if value == "json":
        return "application/fhir+json"
    elif value == "xml":
        return "application/fhir+xml"
    return value  # fallback: use whatever it says


def execute_operation(operation, resource):
    """
    Executes a FHIR operation (CREATE, UPDATE, READ) on the server.

    :param operation: Dictionary containing operation details.
    :param resource: The FHIR resource to operate on.
    :return: HTTP response object.
    :raises: NotImplementedError for unsupported methods.
    """
    method = operation.get("type", {}).get("code", "").lower()
    resource_type = operation.get("resource")
    url = f"{FHIR_SERVER_BASE}/{resource_type}"
    headers = {
        "Content-Type": parse_fhir_header(operation.get("contentType")),
        "Accept": parse_fhir_header(operation.get("accept")),
    }

    if method == "create":
        log_to_file(f"Executing: {method.upper()} {url}")
        response = requests.post(url, headers=headers, json=resource)
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
    elif method == "update":
        resource_id = resource.get("id")
        log_to_file(f"Executing: {method.upper()} {url}/{resource_id}")
        response = requests.put(f"{url}/{resource_id}", headers=headers, json=resource)
    elif method == "read":
        resource_id = resource.get("id")
        log_to_file(f"Executing: {method.upper()} {url}/{resource_id}")
        response = requests.get(f"{url}/{resource_id}", headers=headers)
    else:
        raise NotImplementedError(f"Method {method} not implemented")

    log_to_file(f"Response: {response.status_code}")
    return response


def get_fixture(testscript):
    """
    Extracts fixture definitions from a testscript.

    :param testscript: Testscript dictionary.
    :return: List of fixture dictionaries.
    """
    fixtures = []
    for fixture in testscript.get("fixture", []):
        fixtures.append(fixture)
    return fixtures


def get_testscripts_from_config():
    """
    Loads testscript configurations from config.json or scans Test_Scripts folder.

    :return: List of (testscript_path, fixture_path) tuples.
    """
    CONFIG_PATH = "../config.json"
    TESTSCRIPT_FOLDER = "../Test_Scripts"

    # Load config
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {}

    # Test scripts from the config, if present
    testscripts = config.get("testscripts", [])

    if not testscripts:
        testscripts = [
            os.path.join(TESTSCRIPT_FOLDER, f).replace("\\", "/")
            for f in os.listdir(TESTSCRIPT_FOLDER)
            if f.endswith(".json")
        ]
        print(testscripts)

    request = []

    for ts_path in testscripts:
        with open(ts_path, "r", encoding="utf-8") as f:
            testscript = json.load(f)

        fixtures = get_fixture(testscript)

        if fixtures:
            for fixture in fixtures:
                fixture_ref = fixture.get("resource", {}).get("reference")

                if fixture_ref:
                    # Extract filename (without path)
                    fixture_name = os.path.basename(fixture_ref)

                    # Change the file extension from .html to .json
                    fixture_name = os.path.splitext(fixture_name)[0] + ".json"

                    # Add prefix 'Example_Instances/'
                    fixture_path = os.path.join("Example_Instances", fixture_name)
                    fixture_path = fixture_path.replace("\\", "/")
                    ts_path = ts_path.replace("../", "")
                    request.append((ts_path, fixture_path))

    return request


# Fixture for dynamic test data
@pytest.fixture(params=get_testscripts_from_config())
def testscript_data(request):
    """
    Pytest fixture that provides testscript and resource data for parameterized tests.

    :param request: Pytest fixture request object.
    :return: Tuple of (testscript, resource) data.
    """
    testscript_path, resource_path = request.param
    testscript = load_json(testscript_path)
    resource = load_json(resource_path)
    return testscript, resource


def execute_test_actions(test, resource):
    """
    Executes all actions for a single test.

    :param test: Test definition dictionary.
    :param resource: FHIR resource to test with.
    :return: True if test passed, False otherwise.
    """
    stop_test_on_fail = test.get("stopTestOnFail", False)
    test_name = test.get('name', 'Unnamed Test')
    log_to_file(f"\n ----------- Starting Test: {test_name} -----------")

    response = None
    test_passed = True

    for action_index, action in enumerate(test.get("action", [])):
        try:
            # WHEN – Operation
            if "operation" in action:
                operation = action["operation"]
                response = execute_operation(operation, resource)

                # Extension: If it was a CREATE operation, then check GET
                method = operation.get("type", {}).get("code", "").lower()
                resource_type = operation.get("resource")
                if method == "create":
                    global saved_resource_id
                    assert saved_resource_id, "No ID was saved after create"

                    # GET for verification
                    read_url = f"{FHIR_SERVER_BASE}/{resource_type}/{saved_resource_id}"
                    log_to_file(f"Verifying created resource via GET: {read_url}")
                    get_response = requests.get(read_url, headers={"Accept": "application/fhir+json"})

                    # Output & Assertion
                    log_to_file(f"Response: {get_response.status_code}")
                    try:
                        data = get_response.json()
                        assert data.get("id") == saved_resource_id, "GET returned different ID"
                        assert data.get("resourceType") == resource_type, "ResourceType mismatch"
                    except ValueError:
                        assert False, "GET response is not valid JSON"

            # THEN - Assertion
            elif "assert" in action:
                assertion = action["assert"]
                if "validateProfileId" in assertion:
                    try:
                        validate_profile_assertion(assertion.get("validateProfileId"))
                        log_to_file(f"✓ Assertion passed")
                    except AssertionError as e:
                        test_passed = handle_assertion_error(e, stop_test_on_fail)

                contentType = False
                if "contentType" in assertion:
                    try:
                        contentType = True
                        validate_content_type(response, assertion.get("contentType"))
                        log_to_file(f"✓ Assertion passed")
                    except AssertionError as e:
                        test_passed = handle_assertion_error(e, stop_test_on_fail)

                if assertion.get("direction") == "response" and contentType == False:
                    try:
                        validate_response(assertion, response)
                        log_to_file(f"✓ Assertion  passed")
                    except AssertionError as e:
                        test_passed = handle_assertion_error(e, stop_test_on_fail)

                elif assertion.get("direction") == "request":
                    log_to_file("direction request out of scope")


        except TestExecutionError:
            # Re-raise to stop the test
            raise
        except Exception as e:
            if stop_test_on_fail:
                raise TestExecutionError(f"Test stopped due to stopTestOnFail: {str(e)}")
            else:
                test_passed = False

    return test_passed


def handle_assertion_error(e, stop_test_on_fail):
    """
    Logs the AssertionError and decides whether to stop or continue the test.

    :param e: The AssertionError exception.
    :param stop_test_on_fail: Boolean flag indicating if test should stop on failure.
    :return: True if test should continue, False if test failed.
    :raises: TestExecutionError if stop_test_on_fail is True.
    """
    log_to_file(f"✗ ASSERTION FAILED: {str(e)}")
    if stop_test_on_fail:
        raise TestExecutionError(f"Test stopped due to stopTestOnFail: {str(e)}")
    return False  # Test failed, but continuing allowed


def test_fhir_operations(testscript_data):
    """
    Main test function for FHIR operations testing.
    Executes all tests in a testscript with GIVEN-WHEN-THEN structure.

    :param testscript_data: Tuple containing testscript and resource data.
    """
    # GIVEN
    testscript, resource = testscript_data

    overall_results = []

    for test in testscript.get("test", []):
        test_name = test.get('name', 'Unnamed Test')

        try:
            test_passed = execute_test_actions(test, resource)

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
