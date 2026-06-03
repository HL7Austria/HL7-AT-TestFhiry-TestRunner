"""
Reference parser for FHIR fixtures.
Parses references within fixture bodies to identify dependencies between fixtures.
"""
import json
import re
import xml.etree.ElementTree as ET
from typing import Any, List, Union


def parse_references(body: Union[dict, str], fixture_ids: List[str]) -> List[str]:
    """
    Recursively scans a FHIR resource body for reference fields and extracts
    local fixture IDs that this fixture depends on.

    :param body: The FHIR resource body (dict for JSON, str for XML)
    :param fixture_ids: List of known fixture IDs to check against
    :return: List of fixture_ids that this fixture references
    """
    references = []

    if isinstance(body, dict):
        references = _parse_json_references(body, fixture_ids)
    elif isinstance(body, str):
        # Check if it's XML
        try:
            ET.fromstring(body)
            references = _parse_xml_references(body, fixture_ids)
        except ET.ParseError:
            # Not XML, might be JSON string
            try:
                json_body = json.loads(body)
                references = _parse_json_references(json_body, fixture_ids)
            except (json.JSONDecodeError, TypeError):
                # Not JSON either, skip
                pass

    return references


def _parse_json_references(obj: Any, fixture_ids: List[str], references: List[str] = None) -> List[str]:
    """
    Recursively parses JSON object for reference fields.

    :param obj: The JSON object (dict, list, or primitive)
    :param fixture_ids: List of known fixture IDs
    :param references: Accumulated references (for recursion)
    :return: List of fixture_ids that are referenced
    """
    if references is None:
        references = []

    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "reference" and isinstance(value, str):
                fixture_id = _extract_fixture_id_from_reference(value, fixture_ids)
                if fixture_id and fixture_id not in references:
                    references.append(fixture_id)
            else:
                _parse_json_references(value, fixture_ids, references)
    elif isinstance(obj, list):
        for item in obj:
            _parse_json_references(item, fixture_ids, references)

    return references


def _parse_xml_references(xml_str: str, fixture_ids: List[str]) -> List[str]:
    """
    Parses XML string for reference elements.

    :param xml_str: The XML string
    :param fixture_ids: List of known fixture IDs
    :return: List of fixture_ids that are referenced
    """
    references = []

    # Find all <reference value="..."/> elements
    pattern = r'<reference[^>]*value="([^"]*)"[^>]*/>'
    matches = re.findall(pattern, xml_str)

    for match in matches:
        fixture_id = _extract_fixture_id_from_reference(match, fixture_ids)
        if fixture_id and fixture_id not in references:
            references.append(fixture_id)

    return references


def _extract_fixture_id_from_reference(reference: str, fixture_ids: List[str]) -> str:
    """
    Extracts a fixture ID from a reference string if it matches a known fixture.

    Reference formats:
    - "ResourceType/fixture_id" (e.g., "Patient/HL7ATCorePatientExample01")
    - "fixture_id" (e.g., "HL7ATCorePatientExample01")
    - Absolute URLs (ignored, not local fixtures)

    :param reference: The reference string
    :param fixture_ids: List of known fixture IDs
    :return: The fixture ID if it's a local reference, None otherwise
    """
    # Skip absolute URLs (http://, https://, urn:uuid:, etc.)
    if reference.startswith(("http://", "https://", "urn:")):
        return None

    # Try to extract fixture ID from "ResourceType/fixture_id" format
    if "/" in reference:
        parts = reference.split("/")
        potential_id = parts[-1]
        if potential_id in fixture_ids:
            return potential_id
    else:
        # Direct fixture ID
        if reference in fixture_ids:
            return reference

    return None


def is_reference_to_fixture(reference: str, fixture_ids: List[str]) -> bool:
    """
    Checks if a reference string points to a local fixture.

    :param reference: The reference string
    :param fixture_ids: List of known fixture IDs
    :return: True if reference is to a local fixture, False otherwise
    """
    return _extract_fixture_id_from_reference(reference, fixture_ids) is not None
