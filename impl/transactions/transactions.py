import json
import re
import uuid
import xml.etree.ElementTree as ET

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

def prefix_references_with_urn_uuid_xml(xml_str):
    """
    Prefixes all reference value attributes in an XML FHIR resource with 'urn:uuid:'.

    :param xml_str: Raw XML string of a FHIR resource.
    :return: XML string with prefixed references.
    """
    def _prefix_ref(match):
        ref_value = match.group(2)
        if not ref_value.startswith("urn:uuid:"):
            ref_value = f"urn:uuid:{ref_value}"
        return match.group(1) + ref_value + match.group(3)
    return re.sub(r'(<reference[^>]*value=")([^"]*)(")', _prefix_ref, xml_str)

def build_whole_transaction_bundle_xml(xml_resources: list[str]) -> str:
    """
    Builds a FHIR XML transaction bundle from a list of XML resource strings.
    :param xml_resources: List of raw XML strings of FHIR resources.
    :return: Complete XML transaction bundle as string.
    """
    FHIR_NS = "http://hl7.org/fhir"
    ET.register_namespace('', FHIR_NS)

    bundle = ET.Element(f'{{{FHIR_NS}}}Bundle')
    type_el = ET.SubElement(bundle, f'{{{FHIR_NS}}}type')
    type_el.set('value', 'transaction')

    for xml_str in xml_resources:
        xml_str = prefix_references_with_urn_uuid_xml(xml_str)
        resource_root = ET.fromstring(xml_str)
        resource_type = resource_root.tag.split('}')[-1] if '}' in resource_root.tag else resource_root.tag

        ns = {'fhir': FHIR_NS}
        id_el = resource_root.find('fhir:id', ns) if '}' in resource_root.tag else resource_root.find('id')
        resource_id = id_el.get('value', str(uuid.uuid4())) if id_el is not None else str(uuid.uuid4())

        entry = ET.SubElement(bundle, f'{{{FHIR_NS}}}entry')

        full_url = ET.SubElement(entry, f'{{{FHIR_NS}}}fullUrl')
        full_url.set('value', f'urn:uuid:{resource_type}/{resource_id}')

        resource_wrapper = ET.SubElement(entry, f'{{{FHIR_NS}}}resource')
        resource_wrapper.append(resource_root)

        request = ET.SubElement(entry, f'{{{FHIR_NS}}}request')
        method = ET.SubElement(request, f'{{{FHIR_NS}}}method')
        method.set('value', 'POST')
        url = ET.SubElement(request, f'{{{FHIR_NS}}}url')
        url.set('value', resource_type)

    return ET.tostring(bundle, encoding='unicode', xml_declaration=True)
