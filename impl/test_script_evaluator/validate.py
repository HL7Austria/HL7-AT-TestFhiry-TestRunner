from impl.test_script_evaluator.test_script_evaluator_log_to_file import log_to_file, parse_fhir_header, profile_manager


def validate_content_type(response, expected_type=None):
    """
    Validates whether the server response matches the expected content type.
    If no expected_type is specified, no validation is performed.
    :param response: The HTTP response object returned by the server.
    :param expected_type:  The expected Content-Type (e.g., "json", "xml", or a full MIME type).
                           If None or empty, no validation is performed.
    :return: None
    """

    # If no expected type is specified, skip
    if not expected_type:
        log_to_file("Skipping Content-Type validation (no expected type provided).")
        return

    actual_content_type = response.headers.get("Content-Type", "").split(";")[0].strip()
    expected_type = parse_fhir_header(expected_type)

    log_to_file(f"Checking Content-Type: expected '{expected_type}', got '{actual_content_type}'")

    are_equal = actual_content_type == expected_type  # Python does not create a diff because it does not directly see 'string == string'
    assert are_equal, f"Content-Type mismatch: got '{actual_content_type}', expected '{expected_type}'"


def validate_response(assertion, response):
    """
    Validates HTTP response against assertion rules.

    Checks if response status code matches expected codes from assertion.

    :param assertion: Dictionary containing validation rules with 'responseCode' key.
    :param response: The HTTP response object returned by the server.
    :return: None
    """

    if "responseCode" in assertion:
        expected_codes = [code.strip() for code in assertion.get("responseCode", "").split(",")]
        status_code = str(response.status_code)
        log_to_file(f"Asserting response code {status_code} in {expected_codes}")
        assert status_code in expected_codes, f"Assertion failed: {status_code} not in {expected_codes}"


def validate_profile_assertion(profile_id):
    """
    Validates whether the profile specified in 'validateProfileId' exists.

    :param profile_id: The profile ID to validate (from 'validateProfileId').
    :return: None
    """

    if not profile_id:
        log_to_file("Skipping profile validation (no validateProfileId provided).")
        return True

    available_ids = [p[1] for p in profile_manager.get_profiles()]

    log_to_file(f"Asserting profile Id '{profile_id}' in {available_ids}")
    assert profile_id in available_ids, f"Profile ID '{profile_id}' not found in loaded profiles!\n"
