from pathlib import Path
import os
from datetime import datetime
import json
import xml.etree.ElementTree as ET
from typing import Literal, Optional
import re
from lxml import etree
from jsonpath_ng import parse as jp_parse


"""
everything that is small and modular that is not assertions and is not needed anywhere else
"""

BASE_DIR = Path(__file__).resolve().parent.parent

ContentType = Literal['json', 'xml', 'unknown']
OperationType = Literal['read', 'vread', 'update', 'patch', 'delete', 'history', 'create', 'search', 'capabilities', 'transaction', 'batch', 'operation']
OperationMethod = Literal['get', 'put', 'post', 'patch', 'head', 'delete']

def get_full_path(path:str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    import impl.test_script_evaluator.configuration_manager as conf_man
    config_path = conf_man.get_config_manager().path
    if config_path:
        return Path(config_path) / path
    return BASE_DIR / path

def log_to_file(message: str):
    import impl.test_script_evaluator.configuration_manager as conf_man
    print(message)
    log_path = conf_man.get_config_manager().log_file_path
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def get_fixture(testscript):
    fixtures = []
    for fixture in testscript.get("fixture", []):
        fixtures.append(fixture)
    return fixtures

def get_profile(testscript : dict) -> tuple[list[str], list[str]]:
    """Extracts profile references and their corresponding IDs from a TestScript.

    :param testscript: Parsed TestScript JSON dictionary.
    :returns: Tuple of (profile reference list, profile ID list).
    """
    profiles = []
    profile_ids = []
    for profile in testscript.get("profile",[]):
        profiles.append(profile)
    for prof_id in testscript.get("_profile", []):
        profile_ids.append(prof_id)
    
    return profiles, profile_ids

def get_all_profiles(base_path=None):
        """Scans the Profiles folder and returns paths to all JSON profile files.

        :param base_path: Parent folder containing the Profiles subfolder.
                          If None, falls back to BASE_DIR.
        :returns: List of file path strings for every ``.json`` file in the Profiles folder.
        """
        if base_path:
            PROFILE_FOLDER = str(Path(base_path) / "Profiles")
        else:
            import impl.test_script_evaluator.configuration_manager as conf_man
            config_path = conf_man.get_config_manager().path
            if config_path:
                PROFILE_FOLDER = str(Path(config_path) / "Profiles")
            else:
                PROFILE_FOLDER = str(BASE_DIR / "Profiles")

        profiles = [
            os.path.join(PROFILE_FOLDER, name).replace("\\", "/")
            for name in os.listdir(PROFILE_FOLDER)
            if name.endswith(".json")
                    ]
        return profiles

def get_profile_json(profile_list : list[str], base_path=None):
    """Loads profile JSON files whose ``url`` matches one of the given references.

    Reads every JSON file from the Profiles folder and returns the
    JSON-serialised string of the last matching profile.

    :param profile_list: List of profile canonical URL strings to match against.
    :param base_path: Parent folder containing the Profiles subfolder.
                      If None, falls back to BASE_DIR.
    :returns: JSON string of the matching profile, or an empty list if none matched.
    """

    result = []
    profFiles = []
    temp = []

    profFiles = get_all_profiles(base_path)
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
    """Extracts the list of variable definitions from a TestScript.

    :param testscript: Parsed TestScript JSON dictionary.
    :returns: List of variable dictionaries (empty list if none defined).
    """
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

    full_path = get_full_path(path)
    printInfoJson(path)
    with open(full_path, "r", encoding="utf-8") as f:
        return json.load(f)
    
def load_json_list(paths : list[str]):
    """Loads multiple JSON files from the given paths.

    :param paths: List of relative path strings to JSON files.
    :returns: List of parsed JSON dictionaries, or ``None`` if ``paths`` is empty.
    """
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
    """Detects whether a string contains JSON, XML, or an unknown format.

    :param string: The raw string to inspect.
    :returns: ``'json'``, ``'xml'``, or ``'unknown'``.
    """
    if isinstance(string, dict):
        return "json"
    try:
        json.loads(string)
        return "json"
    except Exception:
        pass

    try:
        ET.fromstring(string)
        return "xml"
    except Exception:
        return "unknown"

def map_method_type(type : OperationType) -> OperationMethod:
    """Maps a FHIR operation type to the corresponding HTTP method.

    :param type: A FHIR operation type
    :returns: The HTTP method string. Defaults to ``'get'`` for unrecognised types.
    """
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
    
def detect_path_type(path: str) -> ContentType:
    """
    Checks if string is Xpath or JsonPath
    """

    if not path or not isinstance(path, str):
        return "unknown"
    
    path = path.strip()

    is_xpath = False
    is_jsonpath = False

    try:
        prefixes = set(re.findall(r'([a-zA-Z_][\w]*):(?!:)', path))
        dummy_ns = {p: f'http://dummy/{p}' for p in prefixes}
        etree.XPath(path, namespaces=dummy_ns)
        is_xpath = True
    except Exception:
        pass

    try:
        jp_parse(path)
        is_jsonpath = True
    except Exception:
        pass

    if is_xpath and not is_jsonpath:
        return "xml"
    if is_jsonpath and not is_xpath:
        return "json"
    if is_xpath and is_jsonpath: #only if both libraries can parse the path
        if "$" in path or path.startswith("@"):
            return "json"
        elif "/" in path:
            return "xml"
    
    return "unknown"
    