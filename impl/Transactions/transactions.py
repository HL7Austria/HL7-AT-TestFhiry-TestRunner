import json
import uuid
import os


def load_resources_from_file(filename):
    """
    Loads FHIR resources from a JSON file.

    :param filename: Path to the JSON file containing FHIR resources.
    :return: List of FHIR resource dictionaries.
    :raises ValueError: If file doesn't contain valid FHIR resources.
    """
    with open(filename, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "resourceType" in data:
        return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"{filename} Contains no valid FHIR resource(s).")


def prefix_references_with_urn_uuid(obj):
    """
     Recursively prefixes all reference fields in a FHIR resource with 'urn:uuid:'.

    :param obj: The dictionary or list to process.
    """
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "reference" and isinstance(value, str):
                if not value.startswith("urn:uuid:"):
                    obj[key] = f"urn:uuid:{value}"
            else:
                prefix_references_with_urn_uuid(value)
    elif isinstance(obj, list):
        for item in obj:
            prefix_references_with_urn_uuid(item)


def create_bundle_entry(resource):
    """
    Creates a Bundle entry for a FHIR resource.

    :param resource: The FHIR resource dictionary.
    :return: Bundle entry dictionary.
    """
    resource_type = resource.get("resourceType")
    resource_id = resource.get("id", str(uuid.uuid4()))
    full_url = f"urn:uuid:{resource_type}/{resource_id}"

    return {
        "fullUrl": full_url,
        "resource": resource,
        "request": {
            "method": "POST",
            "url": resource_type
        }
    }


def build_transaction_bundle(resources):
    """
    Builds a FHIR transaction bundle from a list of resources.

    :param resources: List of FHIR resource dictionaries.
    :return: Complete transaction bundle dictionary.
    """
    for res in resources:
        prefix_references_with_urn_uuid(res)
    entries = [create_bundle_entry(res) for res in resources]
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries
    }


def build_whole_transaction_bundle():
    """
    Loads all FHIR resources from Example_Instances folder and builds a transaction bundle.

    :return: JSON string of the transaction bundle.
    """
    folder = "../Example_Instances"
    all_resources = []

    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            filepath = os.path.join(folder, filename)
            try:
                resources = load_resources_from_file(filepath)
                all_resources.extend(resources)
            except Exception as e:
                print(f"Error loading {filename}: {e}")

    bundle = build_transaction_bundle(all_resources)

    bundle_json = json.dumps(bundle, indent=2, ensure_ascii=False)
    return bundle_json


bundle = build_whole_transaction_bundle()
