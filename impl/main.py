from fhir_test_runner.loader import load_test_script
from fhir_test_runner.parser import parse_fhir_testscript
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
TESTSCRIPT_PATH = os.path.join(BASE_DIR, "testscripts/search_test.json")

FHIR_BASE_URL = "https://hapi.fhir.org/baseR4"

def main():
    print(f"🚀 Lade FHIR TestScript aus: {TESTSCRIPT_PATH}")
    testscript = load_test_script(TESTSCRIPT_PATH)

    test_ids = parse_fhir_testscript(testscript)
    print(f"✅ Gefundene Test-IDs: {test_ids}")

if __name__ == "__main__":
    main()
  