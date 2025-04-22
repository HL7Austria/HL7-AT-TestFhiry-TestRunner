import requests
import json

# 1. TestScript-URL & FHIR-Base-URL
TESTSCRIPT_URL = "https://fhir.hl7.at/r4-core-80-include-testscripts/TestScript-testscript-patient-create-at-core.json"
FHIR_BASE_URL = "https://fhir-r4-test.hl7.at/baseR4"

# 2. Lade das TestScript JSON
def get_testscript_json(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

# 3. Hole Resource-Typ aus test[0].action[0].operation.resource
def extract_resource_type(testscript_json):
    return testscript_json["test"][0]["action"][0]["operation"]["resource"]

# 4. Führe GET auf zusammengesetzte URL aus
def perform_get_request(base_url, resource_type):
    full_url = f"{base_url}/{resource_type}"
    response = requests.get(full_url)
    print(f"GET {full_url}")
    print(f"Status: {response.status_code}")
    print(f"Antwort:\n{response.text[:1000]}...")  # Nur ersten 1000 Zeichen anzeigen
    return response

# MAIN
testscript = get_testscript_json(TESTSCRIPT_URL)
resource_type = extract_resource_type(testscript)
print(f"Gefundene Resource im TestScript: {resource_type}")
print("Führe GET-Anfrage aus ...")
perform_get_request(FHIR_BASE_URL, resource_type)
