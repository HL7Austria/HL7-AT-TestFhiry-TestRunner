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
from profile_manager import ProfileManager
from validate import *
from configuration_manager import get_config_manager, get_fhir_server, get_testscript_pairs, has_fhir_server
from impl.model.configuration import Configuration
from impl.Transactions.transactions import build_whole_transaction_bundle
from impl.model.fixture import Fixture
from utils import *


saved_resource_id = ""
log_filename = f"test_results_{timestamp}.txt"

profile_manager = ProfileManager()
profile_manager.make_profile_list(str(BASE_DIR) + "/Profiles")  # Path to profile

FIXTURES = []

# Init logfile
with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(f"FHIR Test Log - {datetime.now()}\n\n")

FHIR_SERVER_BASE = get_fhir_server()

def extract_test_source_id(test):
    """
    Gibt die sourceId eines einzelnen Test-Objekts zurück.
    Falls mehrere sourceIds existieren, wird die erste zurückgegeben.
    """
    for action in test.get("action", []):
        op = action.get("operation")
        if op and "sourceId" in op:
            return op["sourceId"]

    return None


# Execute operation
def execute_operation(operation, resource, test_id):
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
        fixture = next((fix for fix in FIXTURES if fix.source_id == test_id), None)
        if fixture is None:
            log_to_file("no fixture found in update")
            return None
        resource_id = fixture.server_id
        log_to_file(f"Executing: {method.upper()} {url}/{resource_id}")
        resource["id"] = resource_id
        response = requests.put(f"{url}/{resource_id}", headers=headers, json=resource)

    elif method == "read":
        fixture = next((fix for fix in FIXTURES if fix.source_id == test_id), None)
        if fixture is None:
            log_to_file("No fixture found in read")
            return None
        resource_id = fixture.server_id
        log_to_file(f"Executing: {method.upper()} {url}/{resource_id}")
        response = requests.get(f"{url}/{resource_id}", headers=headers)
    else:
        raise NotImplementedError(f"Method {method} not implemented")

    log_to_file(f"Response: {response.status_code}")
    return response

# Fixture for dynamic test data
@pytest.fixture(params=get_testscript_pairs())
def testscript_data(request):
    """
    Pytest fixture that provides testscript and resource data for parameterized tests.

    :param request: Pytest fixture request object.
    :return: Tuple of (testscript, resource) data.
    """
    testscript_path, resource_path = request.param
    testscript = load_json(testscript_path)
    if resource_path:
        resources = load_json_list(resource_path)
    else:
        resources = None
    return testscript, resources

def execute_test_actions(test, resource, test_id):
    """
    Executes all actions for a single test.

    :param test: Test definition dictionary.
    :param resource: FHIR resource to test with.
    :return: True if test passed, False otherwise.
    """
    #stop_test_on_fail = test.get("stopTestOnFail", False)
    test_name = test.get('name', 'Unnamed Test')
    log_to_file(f"\n ----------- Starting Test: {test_name} -----------")

    response = None
    test_passed = True

    for action_index, action in enumerate(test.get("action", [])):
        try:
            # WHEN – Operation
            if "operation" in action:
                operation = action["operation"]
                response = execute_operation(operation, resource, test_id)

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
                stopTestOnFail = assertion.get("stopTestOnFail", False)
                if "validateProfileId" in assertion:
                    try:
                        validate_profile_assertion(assertion.get("validateProfileId"))
                        log_to_file("✓ Assertion passed")
                    except AssertionError as e:
                        if stopTestOnFail:
                            log_to_file("⚠ stopTestOnFail assertion failed → Test terminated")
                            raise TestExecutionError(str(e))
                        else:
                            test_passed = handle_assertion_error(e, False)

                contentType = False
                if "contentType" in assertion:
                    try:
                        contentType = True
                        validate_content_type(response, assertion.get("contentType"))
                        log_to_file("✓ Assertion passed")
                    except AssertionError as e:
                        if stopTestOnFail:
                            log_to_file("⚠ stopTestOnFail assertion failed → Test terminated")
                            raise TestExecutionError(str(e))
                        else:
                            test_passed = handle_assertion_error(e, False)

                if assertion.get("direction") == "response" and not contentType:
                    try:
                        validate_response(assertion, response)
                        log_to_file("✓ Assertion passed")
                    except AssertionError as e:
                        if stopTestOnFail:
                            log_to_file("⚠ stopTestOnFail assertion failed → Test terminated")
                            raise TestExecutionError(str(e))
                        else:
                            test_passed = handle_assertion_error(e, False)

                elif assertion.get("direction") == "request":
                    log_to_file("direction request out of scope")


        except TestExecutionError:
            # Re-raise to stop the test
            raise
        except Exception as e:
                raise TestExecutionError(f"Test stopped: {str(e)}")


    return test_passed

def save_fixtures(jsonFiles, fix_list):
    """
    saves fixtures to the server and saves infos for them
    :param jsonFiles: the json inside the Files
    """
    bundle_json = [] #die zu erstellenden Fixtures als json
    for jsonf, fixture in zip(jsonFiles, fix_list):
        fix_id = jsonf.get("id")
        fix_source_id = fixture.get("id")
        autocreate = fixture.get("autocreate", True)
        if(autocreate):
            bundle_json.append(jsonf)
        FIXTURES.append(Fixture(fix_id,fix_source_id)) #erstes Anlegen vor bundle

    if bundle_json:
        bundle = build_whole_transaction_bundle(bundle_json)

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
                    fix.server_id = res_id  # speichern der Server id

def extract_fixture_ids(data):
    fixture_ids = []

    if "fixture" not in data:
        return fixture_ids

    for fx in data["fixture"]:
        fixture_ids.append(fx.get("id"))

    return fixture_ids

def handle_assertion_error(e, stop_test_on_fail):
    """
    Logs the AssertionError and decides whether to stop or continue the test.

    :param e: The AssertionError exception.
    :param stop_test_on_fail: Boolean flag indicating if test should stop on failure.
    :return: True if test should continue, False if test failed.
    :raises: TestExecutionError if stop_test_on_fail is True.
    """
    log_to_file(f"✗ ASSERTION FAILED: {str(e)}")
    if stop_test_on_fail == True:
        raise TestExecutionError(f"Test stopped due to stopTestOnFail: {str(e)}")
    return False  # Test failed, but continuing allowed

def test_fhir_operations(testscript_data):
    """
    Main test function for FHIR operations testing.
    Executes all tests in a testscript with GIVEN-WHEN-THEN structure.

    :param testscript_data: Tuple containing testscript and resource data.
    """

    if not has_fhir_server():
        log_to_file("✗ TEST SKIPPED: No FHIR server configured")
        pytest.skip("No FHIR server configured in config.json")
    # GIVEN
    testscript, resources = testscript_data
    if resources != None:
        resource = resources[0] # later there should be a method that decides which fixture will be taken for the test
    else:
        resource = None

    overall_results = []

    fixture_list = get_fixture(testscript)
    if fixture_list: #falls es fixtures gibt
        save_fixtures(resources, fixture_list)


    for test in testscript.get("test", []):
        test_name = test.get('name', 'Unnamed Test')
        test_id = ""
        for action in test.get("action", []):
            operation = action.get("operation")
            if operation and "sourceId" in operation:
                test_id = operation["sourceId"]
                break
        try:
            test_passed = execute_test_actions(test, resource, test_id)

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
