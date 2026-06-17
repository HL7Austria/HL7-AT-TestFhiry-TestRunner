from pathlib import Path
import os
import json
import re
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
    """Resolves a (possibly relative) path to an absolute path.

    If the path is absolute it is returned as-is. Otherwise it is resolved
    relative to the configured base path (from ConfigManager) or the package
    base directory as a fallback.

    :param path: A relative or absolute filesystem path string.
    :returns: A resolved absolute Path.
    """
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

def load_resource(path : str):
    """
    Loads a FHIR resource file (JSON or XML) from the given path.
    :param path: The path to the resource file.
    :return: Parsed JSON content as dict, or raw XML content as str.
    """
    if path.startswith("impl"):
        path = path.replace("impl/", "")
    full_path = get_full_path(path)
    printInfoJson(path)
    with open(full_path, "r", encoding="utf-8") as f:
        if str(full_path).endswith(".xml"):
            return f.read()
        else:
            return json.load(f)

def load_resource_list(paths : list[str]):
    """Loads multiple FHIR resource files (JSON or XML) from the given paths.

    :param paths: List of relative path strings to resource files.
    :returns: List of parsed JSON dicts or raw XML strings, or ``None`` if ``paths`` is empty.
    """
    resource_list = []

    if not paths:
        return None

    for path in paths:
        resource_list.append(load_resource(path))

    return resource_list

def extract_fhir_meta(resource):
    """Extracts id and resourceType from a FHIR resource (dict, JSON string, or XML string).

    :param resource: A parsed JSON dict, JSON string, or raw XML string.
    :returns: Tuple of (resource_id, resource_type).
    """
    if isinstance(resource, list):
        # JSON Patch documents are arrays, not FHIR resources - they don't have id/resourceType
        return None, None
    if isinstance(resource, dict):
        return resource.get("id"), resource.get("resourceType")
    elif string_type(resource) == "json":
        parsed = json.loads(resource)
        return parsed.get("id"), parsed.get("resourceType")
    else:
        # ET für den Resource-Typ (Root-Tag) verwenden
        root = ET.fromstring(resource)
        tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
        
        # Robuste Regex für ID - funktioniert unabhängig von Attribut-Reihenfolge
        # Sucht nach <id> Element mit value-Attribut
        id_match = re.search(r'<id[^>]*\bvalue\s*=\s*["\']([^"\']*)["\']', resource)
        res_id = id_match.group(1) if id_match else ''
        
        return res_id, tag

def string_type(string: (str | dict)) -> ContentType:
    """Detects whether a string contains JSON, XML, or an unknown format.

    :param string: The raw string to inspect.
    :returns: ``'json'``, ``'xml'``, or ``'unknown'``.
    """
    if isinstance(string, dict):
        return "json"
    if isinstance(string, list):
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
        if "$" in path or path.startswith("@") or "." in path:
            return "json"
        elif "/" in path:
            return "xml"
    
    return "unknown"
    