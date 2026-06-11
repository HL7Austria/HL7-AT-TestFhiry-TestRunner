import argparse
import sys
from impl.test_script_evaluator.configuration_manager import init_config_manager, get_config_manager, get_testscript_pairs
from impl.test_script_evaluator.test_script_evaluator_log_to_file import (
    load_testscript_data,
    test_fhir_operations,
)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FHIR TestScript Runner")
    parser.add_argument("--config", required=True, help="Path to config.json")
    args = parser.parse_args()
    try:
        init_config_manager(args.config)
        get_config_manager().init_logging()

        for testscript_path, resource_path in get_testscript_pairs():
            try:
                testscript_data = load_testscript_data(testscript_path, resource_path)
                test_fhir_operations(testscript_data)
            except Exception as e:
                print(e)
    except Exception as e:
        print(str(e))
        sys.exit(1)
