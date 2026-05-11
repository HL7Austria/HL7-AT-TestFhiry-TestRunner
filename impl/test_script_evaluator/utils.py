from pathlib import Path
import os
from datetime import datetime
import json
import xml.etree.ElementTree as ET
from typing import Literal


"""
everything that is small and modular that is not assertions and is not needed anywhere else
"""

BASE_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = BASE_DIR / "Results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
log_filename = f"test_results_{timestamp}.txt"
LOG_FILE_PATH = os.path.abspath(RESULTS_DIR / log_filename)

ContentType = Literal['json', 'xml', 'unknown']
OperationType = Literal['read', 'vread', 'update', 'patch', 'delete', 'history', 'create', 'search', 'capabilities', 'transaction', 'batch', 'operation']
OperationMethod = Literal['get', 'put', 'post', 'patch', 'head', 'delete']

with open(LOG_FILE_PATH, "w", encoding="utf-8") as f:
    f.write(f"FHIR Test Log - {datetime.now()}\n\n")

def get_full_path(path:str) -> Path:
    return BASE_DIR / path

def log_to_file(message: str):
    print(message)
    with open(LOG_FILE_PATH, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def get_fixture(testscript):
    fixtures = []
    for fixture in testscript.get("fixture", []):
        fixtures.append(fixture)
    return fixtures

def get_profile(testscript : dict) -> tuple[list[str], list[str]]:
    profiles = []
    profile_ids = []
    for profile in testscript.get("profile",[]):
        profiles.append(profile)
    for prof_id in testscript.get("_profile", []):
        profile_ids.append(prof_id)
    
    return profiles, profile_ids

def get_all_profiles():
        PROFILE_FOLDER = "impl/Profiles"

        profiles = [
            os.path.join(PROFILE_FOLDER, name).replace("\\", "/")
            for name in os.listdir(PROFILE_FOLDER)
            if name.endswith(".json")
                    ]
        return profiles

def get_profile_json(profile_list : list[str]):#brauch ich das wirklich

    result = []
    profFiles = []
    temp = []

    """
    hier einfach alle files durchgehen --> schaun ob das Profil drinnen is (ob ich referenz oder id nimm noch nicht sicher)
    --> diese Files dann in enine json-list zusammenstecken, dann kann ich später einfach element für element in ein bundle reinschmeißen
    
    with open(full_path, "r", encoding="utf-8") as f:
            json_list.append(json.load(f))
            """
    profFiles = get_all_profiles()
    for file in profFiles:
        with open(file, "r", encoding="utf-8") as f:
            temp.append(json.load(f))
    
    for json_f in temp:
        for p in profile_list:
            if json_f["url"] == p:
                result = json.dumps(json_f)
    
    temp.clear()
    profFiles.clear()
    return result

def get_variables(testscript):
    vars = []
    for var in testscript.get("variable", []):
        vars.append(var)
    return vars

def load_json(path : str):
    """
    Loads a JSON File from the given path.
    :param path: The path to the JSON file.
    :return: Parsed JSON content as dictionary.
    """

    if path.startswith("impl"):
        path = path.replace("impl/", "")
    print(path)

    if path.startswith("impl"):
        path = path.replace("impl/", "")
    print(path)
    full_path = get_full_path(path)
    printInfoJson(path)
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def load_json_list(paths : list[str]):
    json_list = []

    if not paths:
        return None

    for path in paths:
        full_path = get_full_path(path)
        printInfoJson(path)

        with open(full_path, "r", encoding="utf-8") as f:
            json_list.append(json.load(f))

    return json_list

def printInfoJson(path : str):
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

def parse_fhir_header(value : str):
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

def string_type(string: str) -> ContentType:
    try:
        json.loads(string)
        return "json"
    except json.JSONDecodeError:
        pass

    try:
        ET.fromstring(string)
        return "xml"
    except ET.ParseError:
        return "unknown"

def map_method_type(type : OperationType) -> OperationMethod:
    if type == "update":
        return "put"
    elif type == "delete":
        return "delete"
    elif type == "patch":
        return "patch"
    elif type == "create" or type == "batch" or type == "transaction" or type == "operation":
        return "post"
    else:
        return "get"
    