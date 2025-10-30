import json
import requests
import pytest
from pathlib import Path
import os
from datetime import datetime

from numpy.ma.testutils import assert_equal

from Transactions.transactions import *
from model.configuration import Configuration

FHIR_SERVER_BASE = "http://cql-sandbox.projekte.fh-hagenberg.at:8080/fhir"
saved_resource_id = ""
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"test_results_{timestamp}.txt"



BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "Results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE_PATH = RESULTS_DIR / log_filename
LOG_FILE_PATH = os.path.abspath(LOG_FILE_PATH)

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
    print(f"Lade JSON: {full_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)



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

    log_to_file(f"Executing: {method.upper()} {url}")

    if method == "create":
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
        response = requests.put(f"{url}/{resource_id}", headers=headers, json=resource)
    elif method == "read":
        resource_id = resource.get("id")
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


# Fixture for dynamic test data
@pytest.fixture(params=[
    # ("Test_Scripts/TestScript-testscript-patient-create-at-core.json",
    # "Example_Instances/Patient-HL7ATCorePatientUpdateTestExample.json"),
    # ("Test_Scripts/TestScript-testscript-patient-update-at-core.json",
    # "Example_Instances/Patient-HL7ATCorePatientUpdateTestExample.json")
    ("Test_Scripts/TestScript-testscript-assert-contentType-json.json",
     "Example_Instances/Patient-HL7ATCorePatientUpdateTestExample.json")
    # ("Test_Scripts/TestScript-testscript-assert-contentType-xml.json",
    #   "Example_Instances/Patient-HL7ATCorePatientUpdateTestExample.json"),
    ])
def testscript_data(request):
    testscript_path, resource_path = request.param
    testscript = load_json(testscript_path)
    resource = load_json(resource_path)
    return testscript, resource


# The actual test case - structured in GIVEN-WHEN-THEN
def test_fhir_operations(testscript_data):
    # Build Transaction Bundle
    bundle = build_whole_transaction_bundle()

    response = requests.post(
        FHIR_SERVER_BASE,
        headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"},
        json=json.loads(bundle)
    )

    # GIVEN
    testscript, resource = testscript_data

    for test in testscript.get("test", []):

        log_to_file(f"\n Test: {test.get('name')}")
        response = None

        try:
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
                    if assertion.get("direction") == "response":
                        validate_response(assertion, response)
                    elif assertion.get("direction") == "request":
                        print("direction request out of scope")
                        log_to_file("direction request out of scope")

            # Log success if all actions passed
            log_to_file("PASSED")

        except AssertionError as e:
            log_to_file(f"FAILED: {str(e)}")
            raise  # re-raise to keep pytest aware of test failure
