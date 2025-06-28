import json
import uuid
import os


def load_resources_from_file(filename):
    with open(filename, encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "resourceType" in data:
        return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError(f"{filename} enthält keine gültige(n) FHIR-Ressource(n).")

def prefix_references_with_urn_uuid(obj):
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
    for res in resources:
        prefix_references_with_urn_uuid(res)
    entries = [create_bundle_entry(res) for res in resources]
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries
    }

def build_whole_transaction_bundle():
    folder = "../Example_Instances"
    all_resources = []

    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            filepath = os.path.join(folder, filename)
            try:
                resources = load_resources_from_file(filepath)
                all_resources.extend(resources)
            except Exception as e:
                print(f"Fehler beim Laden von {filename}: {e}")

    bundle = build_transaction_bundle(all_resources)

    bundle_json = json.dumps(bundle, indent=2, ensure_ascii=False)
    return bundle_json

