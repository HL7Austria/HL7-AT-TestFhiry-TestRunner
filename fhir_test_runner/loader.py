import json

def load_test_script(file_path):
    """Lädt ein FHIR TestScript JSON."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
