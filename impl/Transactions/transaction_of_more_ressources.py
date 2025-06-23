import json
import uuid

def load_resources_from_file(filename):
    with open(filename, encoding="utf-8") as f:
        data = json.load(f)

    # Wenn nur ein einzelnes Objekt, dann Liste daraus machen
    if isinstance(data, dict) and "resourceType" in data:
        return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError("Datei enthält keine gültige(n) FHIR-Ressource(n).")

def create_bundle_entry(resource):
    resource_type = resource.get("resourceType")
    resource_id = resource.get("id", str(uuid.uuid4()))
    full_url = f"urn:uuid:{resource_id}"

    return {
        "fullUrl": full_url,
        "resource": resource,
        "request": {
            "method": "POST",  # Alternativ: "PUT", je nach Use-Case
            "url": resource_type
        }
    }

def build_transaction_bundle(resources):
    entries = [create_bundle_entry(res) for res in resources]

    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries
    }

    return bundle

if __name__ == "__main__":
    filename = "Patient-HL7ATCorePatientUpdateTestExample.json"
    resources = load_resources_from_file(filename)
    bundle = build_transaction_bundle(resources)

    # Ausgabe als JSON-String
    bundle_json = json.dumps(bundle, indent=2, ensure_ascii=False)
    print(bundle_json)
