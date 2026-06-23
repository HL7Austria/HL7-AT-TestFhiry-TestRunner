import argparse
import sys
from impl.test_script_evaluator.configuration_manager import init_config_manager, get_testscript_pairs
from impl.test_script_evaluator.test_script_evaluator_log_to_file import (
    load_testscript_data,
    test_fhir_operations,
)
import impl.test_script_evaluator.result_tracker as rt
import impl.test_script_evaluator.junit_logger as logger

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FHIR TestScript Runner")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--novalidator", action="store_true", help="Disable all profile validation")
    args = parser.parse_args()
    tracker = None
    try:
        disable_validation = args.novalidator
        init_config_manager(args.config, disable_validation)
        tracker = rt.init_result_tracker()
        tracker.initialize_test_run()
        for testscript_path, resource_path in get_testscript_pairs():
            try:
                testscript_data = load_testscript_data(testscript_path, resource_path)
                test_fhir_operations(testscript_data, testscript_path)
            except Exception as e:
                print(e)
    except Exception as e:
        print(str(e))
        sys.exit(1)
    finally:
        if tracker is not None:
            try:
                logger.fill_and_save(tracker)
            except Exception as e:
                print(f"Error while saving the JUnit XML: {e}")
                raise
