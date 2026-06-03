"""
Dependency resolver for FHIR fixtures.
Resolves creation order based on fixture references and replaces placeholder references with server IDs.
"""
import json
import re
from collections import deque
from typing import Any, Dict, List, Union

import impl.exception.Error as error
from impl.model.fixture import Fixture


def resolve_creation_order(fixtures: List[Fixture]) -> List[Fixture]:
    """
    Determines the correct creation order for fixtures based on their dependencies.
    Uses topological sort to ensure fixtures are created after their dependencies.

    :param fixtures: List of Fixture objects
    :return: Ordered list of fixtures for creation
    :raises CircularDependencyError: If fixtures reference each other in a cycle
    """
    # Build dependency graph: fixture_id -> list of fixture_ids it depends on
    dependency_graph = {}
    fixture_id_to_fixture = {}

    for fixture in fixtures:
        dependency_graph[fixture.fixture_id] = fixture.references
        fixture_id_to_fixture[fixture.fixture_id] = fixture

    # Perform topological sort using Kahn's algorithm
    in_degree = {fixture_id: 0 for fixture_id in dependency_graph}

    # Calculate in-degrees
    for fixture_id in dependency_graph:
        for dependency in dependency_graph[fixture_id]:
            if dependency in in_degree:
                in_degree[fixture_id] += 1

    # Initialize queue with fixtures that have no dependencies
    queue = deque([fixture_id for fixture_id, degree in in_degree.items() if degree == 0])
    sorted_order = []

    while queue:
        current_id = queue.popleft()
        sorted_order.append(fixture_id_to_fixture[current_id])

        # Reduce in-degree for dependent fixtures
        for fixture_id in dependency_graph:
            if current_id in dependency_graph[fixture_id]:
                in_degree[fixture_id] -= 1
                if in_degree[fixture_id] == 0:
                    queue.append(fixture_id)

    # Check for circular dependencies
    if len(sorted_order) != len(fixtures):
        # Find fixtures that weren't sorted (part of cycle)
        unsorted = set(fixture_id_to_fixture.keys()) - set(f.fixture_id for f in sorted_order)
        raise error.CircularDependencyError(
            f"Circular dependency detected among fixtures: {unsorted}. "
            "Please check fixture references to resolve the cycle."
        )

    return sorted_order


def replace_references(body: Union[dict, str], fixture_id_to_server_id: Dict[str, str]) -> Union[dict, str]:
    """
    Replaces placeholder references in a fixture body with actual server IDs.

    :param body: The fixture body (dict for JSON, str for XML)
    :param fixture_id_to_server_id: Mapping of fixture_id to server_id
    :return: Modified body with resolved references
    """
    if isinstance(body, dict):
        return _replace_json_references(body, fixture_id_to_server_id)
    elif isinstance(body, str):
        # Try XML first
        try:
            import xml.etree.ElementTree as ET
            ET.fromstring(body)
            return _replace_xml_references(body, fixture_id_to_server_id)
        except ET.ParseError:
            # Not XML, might be JSON string
            try:
                json_body = json.loads(body)
                resolved = _replace_json_references(json_body, fixture_id_to_server_id)
                return json.dumps(resolved, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                # Not JSON either, return as-is
                return body
        except Exception:
            # Other XML parsing error, try JSON
            try:
                json_body = json.loads(body)
                resolved = _replace_json_references(json_body, fixture_id_to_server_id)
                return json.dumps(resolved, ensure_ascii=False)
            except (json.JSONDecodeError, TypeError):
                # Not JSON either, return as-is
                return body
    else:
        return body


def _replace_json_references(obj: Any, fixture_id_to_server_id: Dict[str, str]) -> Any:
    """
    Recursively replaces references in a JSON object.

    :param obj: The JSON object (dict, list, or primitive)
    :param fixture_id_to_server_id: Mapping of fixture_id to server_id
    :return: Modified object with resolved references
    """
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key == "reference" and isinstance(value, str):
                result[key] = _resolve_reference_value(value, fixture_id_to_server_id)
            else:
                result[key] = _replace_json_references(value, fixture_id_to_server_id)
        return result
    elif isinstance(obj, list):
        return [_replace_json_references(item, fixture_id_to_server_id) for item in obj]
    else:
        return obj


def _replace_xml_references(xml_str: str, fixture_id_to_server_id: Dict[str, str]) -> str:
    """
    Replaces references in an XML string.

    :param xml_str: The XML string
    :param fixture_id_to_server_id: Mapping of fixture_id to server_id
    :return: Modified XML string with resolved references
    """
    def replace_ref(match):
        prefix = match.group(1)
        ref_value = match.group(2)
        suffix = match.group(3)
        resolved = _resolve_reference_value(ref_value, fixture_id_to_server_id)
        return f'{prefix}{resolved}{suffix}'

    # Replace <reference value="..."/> elements
    pattern = r'(<reference[^>]*value=")([^"]*)("[^>]*/>)'
    return re.sub(pattern, replace_ref, xml_str)


def _resolve_reference_value(reference: str, fixture_id_to_server_id: Dict[str, str]) -> str:
    """
    Resolves a reference value by replacing fixture IDs with server IDs.

    :param reference: The reference string (e.g., "Patient/HL7ATCorePatientExample01")
    :param fixture_id_to_server_id: Mapping of fixture_id to server_id
    :return: Resolved reference string
    """
    # Skip absolute URLs and urn:uuid references
    if reference.startswith(("http://", "https://", "urn:")):
        return reference

    # Try to extract and replace fixture ID
    if "/" in reference:
        parts = reference.split("/")
        resource_type = parts[0]
        fixture_id = parts[-1]

        if fixture_id in fixture_id_to_server_id:
            server_id = fixture_id_to_server_id[fixture_id]
            return f"{resource_type}/{server_id}"
    else:
        # Direct fixture ID reference
        if reference in fixture_id_to_server_id:
            return fixture_id_to_server_id[reference]

    return reference


def validate_all_references_resolved(fixtures: List[Fixture]) -> None:
    """
    Validates that all autocreate fixtures have their references resolved.

    :param fixtures: List of Fixture objects
    :raises UnresolvedReferenceError: If any autocreate fixture has unsolved references
    """
    for fixture in fixtures:
        # Check if this is an autocreate fixture with unresolved references
        if fixture.autodelete and not fixture.references_resolved:
            if fixture.references:
                raise error.UnresolvedReferenceError(
                    f"Autocreate fixture '{fixture.fixture_id}' (source_id: {fixture.source_id}) "
                    f"has unresolved references: {fixture.references}. "
                    "All references must be resolved before the fixture can be used."
                )
