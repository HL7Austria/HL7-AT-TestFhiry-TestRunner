from pathlib import Path
import os
from datetime import datetime
import json

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "Results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"test_results_{timestamp}.txt"
LOG_FILE_PATH = os.path.abspath(RESULTS_DIR / log_filename)

with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(f"FHIR Test Log - {datetime.now()}\n\n")


def log_to_file(message: str):
    print(message)
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def get_fixture(testscript):
    fixtures = []
    for fixture in testscript.get("fixture", []):
        fixtures.append(fixture)
    return fixtures

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
