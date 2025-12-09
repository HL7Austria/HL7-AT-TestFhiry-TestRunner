import json
import requests
import pytest
from pathlib import Path
import os
from datetime import datetime
import traceback

from numpy.ma.testutils import assert_equal
from impl.Transactions.transactions import *
from impl.exception.TestExecutionError import TestExecutionError
from impl.model.configuration import Configuration
from impl.Transactions.transactions import build_whole_transaction_bundle
from impl.model.fixture import Fixture

FHIR_SERVER_BASE = "http://cql-sandbox.projekte.fh-hagenberg.at:8080/fhir"
saved_resource_id = ""
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"test_results_{timestamp}.txt"



BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "Results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE_PATH = RESULTS_DIR / log_filename
LOG_FILE_PATH = os.path.abspath(LOG_FILE_PATH)

FIXTURES = []

# Init logfile
with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(f"FHIR Test Log - {datetime.now()}\n\n")


def log_to_file(message):
    print(message)
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(message + "\n")


# Help function for loading JSON files
def load_json(path):
    full_path = BASE_DIR / path
    printInfoJson(path)
    #print(f"Load: {path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_json_list(paths):
    json_list = []

    if not paths:
        return None

    for path in paths:
        full_path = BASE_DIR / path
        printInfoJson(path)

        with open(full_path, "r", encoding="utf-8") as f:
            json_list.append(json.load(f))

    return json_list



def printInfoJson(path):
    if "Test_Scripts" in str(path):
        filename = os.path.basename(path)
        name_without_extension = os.path.splitext(filename)[0]
        log_to_file(f"\n\n=========== Starting Testscript: {name_without_extension} ===========")
    if "Example_Instances" in str(path):
        log_to_file(f"Load Example Instance: {path}")
    if "Profiles" in str(path):
        log_to_file(f"Load Profile: {path}")

# Mapping of short forms such as ‘json’ to FHIR-compliant MIME types
def parse_fhir_header(value, header_type):
    if not value:
        return "application/fhir+json"
    value = value.lower()
    if value == "json":
        return "application/fhir+json"
    elif value == "xml":
        return "application/fhir+xml"
    return value  # fallback: use whatever it says

# Execute operation
def execute_operation(operation, resource):
    method = operation.get("type", {}).get("code", "").lower()
    resource_type = operation.get("resource")
    url = f"{FHIR_SERVER_BASE}/{resource_type}"
    headers = {
        "Content-Type": parse_fhir_header(operation.get("contentType"), "Content-Type"),
        "Accept": parse_fhir_header(operation.get("accept"), "Accept"),
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
    expected_type = parse_fhir_header(expected_type, "Content-Type")

    log_to_file(f"Checking Content-Type: expected '{expected_type}', got '{actual_content_type}'")

    assert actual_content_type == expected_type, (
        f"Content-Type mismatch: got '{actual_content_type}', expected '{expected_type}'"
    )


# Check assertion
def validate_response(assertion, response):
    # Only check status code if responseCode is present
    if "responseCode" in assertion:
        expected_codes = [code.strip() for code in assertion.get("responseCode", "").split(",")]
        status_code = str(response.status_code)
        log_to_file(f"Asserting response code {status_code} in {expected_codes}")
        assert status_code in expected_codes, f"Assertion failed: {status_code} not in {expected_codes}"

    # Only check content type if contentType is present
    if "contentType" in assertion:
        validate_content_type(response, assertion.get("contentType"))

def get_fixture(testscript):
    fixtures = []
    for fixture in testscript.get("fixture", []):
        fixtures.append(fixture)
    return fixtures


def get_testscripts_from_config():
    CONFIG_PATH = "../config.json"
    TESTSCRIPT_FOLDER = "../Test_Scripts"

    # Config laden
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as config_file:
            config = json.load(config_file)
    except FileNotFoundError:
        config = {}
    except json.decoder.JSONDecodeError as e:
        message = (
            "INVALID JSON\n"
            f"File: {CONFIG_PATH}\n"
            f"Error: {e.msg}\n"
            f"Line: {e.lineno}, Column: {e.colno}\n"
        )
        # in dein Log schreiben
        log_to_file(message)

    # Testscripts aus der Config ODER Ordner
    testscripts = config.get("testscripts", [])

    if not testscripts:
        testscripts = [
            os.path.join(TESTSCRIPT_FOLDER, name).replace("\\", "/")
            for name in os.listdir(TESTSCRIPT_FOLDER)
            if name.endswith(".json")
        ]

    result = []

    for ts_path in testscripts:

        # Testscript laden
        try:
            with open(ts_path, "r", encoding="utf-8") as ts_file:
                testscript = json.load(ts_file)
        except json.decoder.JSONDecodeError as e:
            message = (
                "INVALID JSON\n"
                f"File: {ts_path}\n"
                f"Error: {e.msg}\n"
                f"Line: {e.lineno}, Column: {e.colno}\n"

            )
            # in dein Log schreiben
            log_to_file(message)


        fixtures_raw = get_fixture(testscript)
        fixture_list = []

        for fixture in fixtures_raw:
            fixture_ref = fixture.get("resource", {}).get("reference")

            if fixture_ref:
                filename = os.path.splitext(os.path.basename(fixture_ref))[0] + ".json"
                fixture_path = f"Example_Instances/{filename}".replace("\\", "/")
                fixture_list.append(fixture_path)

        ts_path_clean = ts_path.replace("../", "")

        result.append((ts_path_clean, fixture_list))

    return result


# Fixture for dynamic test data
@pytest.fixture(params=get_testscripts_from_config())
def testscript_data(request):
    testscript_path, resource_path = request.param
    print (resource_path)
    testscript = load_json(testscript_path)
    if resource_path:
        resources = load_json_list(resource_path)
    else:
        resources = None
    return testscript, resources


def execute_test_actions(test, resource):
    """Execute all actions for a single test with stopTestOnFail handling"""
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
                if assertion.get("direction") == "response":
                    try:
                        validate_response(assertion, response)
                        log_to_file(f"✓ Assertion {action_index + 1} passed")
                    except AssertionError as e:
                        log_to_file(f"✗ ASSERTION FAILED: {str(e)}")
                        if stop_test_on_fail:
                            # Stop this test immediately
                            raise TestExecutionError(f"Test stopped due to stopTestOnFail: {str(e)}")
                        else:
                            # Continue with next action but mark test as failed
                            test_passed = False

                elif assertion.get("direction") == "request":
                    log_to_file("direction request out of scope")

        except TestExecutionError:
            # Re-raise to stop the test
            raise
        except Exception as e:
            log_to_file(f"✗ ERROR in action {action_index + 1}: {str(e)}")
            if stop_test_on_fail:
                raise TestExecutionError(f"Test stopped due to stopTestOnFail: {str(e)}")
            else:
                test_passed = False

    return test_passed

def save_fixtures(filenames):
    bundle = build_whole_transaction_bundle(filenames)

    response = requests.post(
        FHIR_SERVER_BASE,
        headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"},
        json=json.loads(bundle)
    )

    results = response.json().get("entry")

    for fix_path, res in zip(filenames, results):
        resp = res.get("response")
        res_loc = resp.get("location")
        res_id = res_loc.split("/")[1]
        FIXTURES.append(Fixture(fix_path, res_id))

# The actual test case - structured in GIVEN-WHEN-THEN
def test_fhir_operations(testscript_data):
    # GIVEN
    testscript, resources = testscript_data
    if resources != None:
        resource = resources[0] # later there should be a method that decides which fixture will be taken for the test
    else:
        resource = None

    overall_results = []

    filenames = ["Organization-Organization-example-f001-burgers.json",
                 "Patient-HL7ATCorePatientExample06-GenderExtension.json", "Patient-HL7ATCorePatientExample01.json"]
    # dass ist die liste an fixtures die dann weitergegeben wird an transactions
    # --> Leni hier musst du dann die fixture-path reintun (also die liste an fixtures die erstellt werden müssen)
    # --> für den Test zumindest, nachher macht das autocreate
    save_fixtures(filenames)  # --> für jedes testscript werden die eigenen Fixtures gespeichert
    #  --> in der Fixture kann unter source_id  die id die es in diesen Testscript hat gespeichert werden!!

    for test in testscript.get("test", []):
        test_name = test.get('name', 'Unnamed Test')

        try:
            test_passed = execute_test_actions(test, resource)
            for action in test.get("action", []):
                # WHEN – Wenn Operation
                if "operation" in action:
                    operation = action["operation"]
                    response = execute_operation(operation, resource)

                    #  Extension: If it was a CREATE operation, then check GET
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

                # THEN - If Assertion
                elif "assert" in action:
                    assertion = action["assert"]
                    direction = assertion.get("direction", "").lower()

                    # Completely skip if direction is 'request' (out of scope)
                    if direction == "request":
                        log_to_file("Skipping assertion (direction: request – out of scope).")
                        continue  #

                    # Validate normal response assertions
                    if direction == "response" or not direction:
                        validate_response(assertion, response)

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
    FIXTURES.clear() #reset for next testscript
