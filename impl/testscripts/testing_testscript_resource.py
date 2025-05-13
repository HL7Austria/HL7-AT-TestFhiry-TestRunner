import json
import requests
import pytest

FHIR_SERVER_BASE = "https://hapi.fhir.org/baseR5"

# Hilfsfunktion zum Laden von JSON-Dateien
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Mapping von Kurzformen wie "json" zu FHIR-konformen MIME-Types
def parse_fhir_header(value, header_type):
    if not value:
        return "application/fhir+json"
    value = value.lower()
    if value == "json":
        return "application/fhir+json"
    elif value == "xml":
        return "application/fhir+xml"
    return value  # fallback: nutze, was auch immer drinsteht


# Operation ausführen
def execute_operation(operation, resource):
    method = operation.get("type", {}).get("code", "").lower()
    resource_type = operation.get("resource")
    url = f"{FHIR_SERVER_BASE}/{resource_type}"
    headers = {
        "Content-Type": parse_fhir_header(operation.get("contentType"), "Content-Type"),
        "Accept": parse_fhir_header(operation.get("accept"), "Accept"),

    }

    print(f"Executing: {method.upper()} {url}")
    if method == "create":
        response = requests.post(url, headers=headers, json=resource)
    elif method == "update":
        resource_id = resource.get("id")
        response = requests.put(f"{url}/{resource_id}", headers=headers, json=resource)
    elif method == "read":
        resource_id = resource.get("id")
        response = requests.get(f"{url}/{resource_id}", headers=headers)
    else:
        raise NotImplementedError(f"Method {method} not implemented")

    print(f"Response: {response.status_code}")
    return response

# Assertion prüfen
def validate_response(assertion, response):
    expected_codes = [code.strip() for code in assertion.get("responseCode", "").split(",")]
    status_code = str(response.status_code)
    print(f"Asserting response code {status_code} in {expected_codes}")
    assert status_code in expected_codes, f"Assertion failed: {status_code} not in {expected_codes}"

# Fixture für dynamische Testdaten
@pytest.fixture(params=[
    ("TestScript-testscript-patient-create-at-core.json", "Patient-HL7ATCorePatientUpdateTestExample.json"),
    ("TestScript-testscript-patient-update-at-core.json", "Patient-HL7ATCorePatientUpdateTestExample.json")
])
def testscript_data(request):
    testscript_path, resource_path = request.param
    testscript = load_json(testscript_path)
    resource = load_json(resource_path)
    return testscript, resource

# Der eigentliche Testfall – strukturiert in GIVEN-WHEN-THEN
def test_fhir_operations(testscript_data):
    # GIVEN
    testscript, resource = testscript_data

    for test in testscript.get("test", []):
        print(f"\n🧪 Test: {test.get('name')}")
        response = None

        for action in test.get("action", []):
            # WHEN – Wenn Operation
            if "operation" in action:
                operation = action["operation"]
                response = execute_operation(operation, resource)

            # THEN – Wenn Assertion
            elif "assert" in action:
                assertion = action["assert"]
                if assertion.get("direction") == "response":
                    validate_response(assertion, response)
                elif assertion.get("direction") == "request":
                    pass  # ggf. später erweitern
