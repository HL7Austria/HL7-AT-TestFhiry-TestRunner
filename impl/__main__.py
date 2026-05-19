from impl.test_script_evaluator.configuration_manager import get_testscript_pairs
from impl.test_script_evaluator.test_script_evaluator_log_to_file import (
    load_testscript_data,
    test_fhir_operations,
)

if __name__ == "__main__":
    for testscript_path, resource_path in get_testscript_pairs():
        testscript_data = load_testscript_data(testscript_path, resource_path)
        test_fhir_operations(testscript_data)
