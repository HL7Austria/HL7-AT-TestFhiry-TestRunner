def parse_fhir_testscript(testscript):
    """Parst die IDs der Tests im FHIR TestScript."""
    test_ids = []
    
    # Prüfe, ob "test" existiert und eine Liste ist
    if "test" in testscript and isinstance(testscript["test"], list):
        for test in testscript["test"]:
            test_id = test.get("id", "Keine ID gefunden")
            test_ids.append(test_id)
    
    return test_ids
