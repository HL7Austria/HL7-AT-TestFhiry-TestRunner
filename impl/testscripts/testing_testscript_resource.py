import json
import requests

# 1. Here you define the URL of your FHIR server against which you want to test
FHIR_SERVER_BASE = "https://hapi.fhir.org/baseR5"


# 2. Helper function for loading a JSON file
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# 3. Main function: executes the test script and applies it to the given resource
def run_testscript(testscript_path, resource_path):
    # 3.1 TestScript is loaded
    testscript = load_json(testscript_path)

    # 3.2 The patient resource is loaded
    resource = load_json(resource_path)

    # 3.3 For each test block in the test script (there can be several)
    for test in testscript.get("test", []):
        print(f"\n🧪 Test: {test.get('name')}")

        response = None  # Cache for the HTTP response

        # 3.4 Each test contains a list of `action`s (operation or assert)
        for action in test.get("action", []):

            # 3.4.1 If an operation block occurs → execute API call
            if "operation" in action:
                operation = action["operation"]
                response = execute_operation(operation, resource)

            # 3.4.2 If an assert block occurs → check
            elif "assert" in action:
                assertion = action["assert"]

                # Only if the assertion target concerns the response
                if assertion.get("direction") == "response":
                    validate_response(assertion, response)
                elif assertion.get("direction") == "request":
                    #validate_request(assertion, resource)
                    pass



# 4. This function executes the actual HTTP call
def execute_operation(operation, resource):
    # 4.1 The HTTP method is determined from the operation type
    method = operation.get("type", {}).get("code", "").lower()

    # 4.2 The resource type
    resource_type = operation.get("resource")
    url = f"{FHIR_SERVER_BASE}/{resource_type}"

    # 4.3 Configure headers for JSON-FHIR communication
    headers = {
        "Content-Type": operation.get("contentType", "application/fhir+json"),
        "Accept": operation.get("accept", "application/fhir+json"),
    }

    print(f"Executing: {method.upper()} {url}")

    # 4.4 Different behavior depending on the method:
    if method == "create":
        # POST → neue Ressource erzeugen
        response = requests.post(url, headers=headers, json=resource)

    elif method == "update":
        # PUT → update existing resource (ID must exist)
        resource_id = resource.get("id")
        response = requests.put(f"{url}/{resource_id}", headers=headers, json=resource)

    elif method == "read":
        # GET → retrieve existing resource (ID must exist)
        resource_id = resource.get("id")
        response = requests.get(f"{url}/{resource_id}", headers=headers)

    else:
        # Other methods are not yet implemented
        raise NotImplementedError(f"Method {method} not implemented")

    # 4.5 Response is returned to be checked later
    print(f"Response: {response.status_code}")
    return response


# 5. This function checks if the actual HTTP status code is correct
def validate_response(assertion, response):
    # 5.1 Extract expected codes from the test script
    expected_codes = [code.strip() for code in assertion.get("responseCode", "").split(",")]

    # 5.2 Actual return code from HTTP response
    status_code = str(response.status_code)

    print(f"Asserting response code {status_code} in {expected_codes}")

    # 5.3 Comparison → Throw error if not included
    if status_code not in expected_codes:
        raise AssertionError(f"Assertion failed: {status_code} not in {expected_codes}")
    else:
        print("Assertion passed")



if __name__ == "__main__":
    run_testscript("TestScript-testscript-patient-create-at-core.json",
                   "Patient-HL7ATCorePatientUpdateTestExample.json")
    run_testscript("TestScript-testscript-patient-update-at-core.json",
                   "Patient-HL7ATCorePatientUpdateTestExample.json")
