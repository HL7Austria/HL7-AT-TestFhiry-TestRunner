import json
import uuid

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

def build_whole_transaction_bundle(jsonFiles):
    """
    builds a bundle for transaction, for saving multiple Example Instances
    :param jsonFiles: json of the Example Instances
    :return: a bundle for saving FHIR-Resources
    """
    all_resources = []

    for file in jsonFiles:
        all_resources.append(file)

    bundle = build_transaction_bundle(all_resources)

    bundle_json = json.dumps(bundle, indent=2, ensure_ascii=False)
    return bundle_json
