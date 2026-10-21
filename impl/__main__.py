import argparse
import logging
import sys
from impl.test_script_evaluator.configuration_manager import init_config_manager, get_config_manager, get_testscript_pairs
from impl.test_script_evaluator.test_script_evaluator_log_to_file import (
    load_testscript_data,
    test_fhir_operations,
)
import impl.test_script_evaluator.result_tracker as rt
import impl.test_script_evaluator.junit_logger as logger
import impl.test_script_evaluator.summary_logger as summary_logger
import impl.test_script_evaluator.log_setup as log_setup
import impl.test_script_evaluator.communication_logger as comm_log

log = logging.getLogger("testrunner")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FHIR TestScript Runner")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--novalidator", action="store_true", help="Disable all profile validation")
    args = parser.parse_args()
    log_setup.setup_console()
    tracker = None
    log_file = None
    comm_dir = None
    try:
        disable_validation = args.novalidator
        init_config_manager(args.config, disable_validation)
        tracker = rt.init_result_tracker()
        tracker.initialize_test_run()
        run_stamp = tracker.run_file_stamp()
        log_file, comm_dir = log_setup.start_run(get_config_manager(), run_stamp)
        log_setup.log_configuration(get_config_manager(), run_stamp, log_file, comm_dir)
        testscript_pairs = get_testscript_pairs()
        log_setup.log_testscripts(testscript_pairs)
        for index, (testscript_path, resource_path) in enumerate(testscript_pairs, start=1):
            log.info("===== TestScript %d/%d: %s", index, len(testscript_pairs), testscript_path)
            comm_log.start_testscript(index, testscript_path)
            try:
                testscript_data = load_testscript_data(testscript_path, resource_path)
                test_fhir_operations(testscript_data, testscript_path)
            except Exception as e:
                log.error("TestScript %s could not be run (%s): %s", testscript_path, type(e).__name__, e)
                log.debug("Traceback:", exc_info=True)
    except Exception as e:
        log.critical("%s", e)
        log.debug("Traceback:", exc_info=True)
        sys.exit(1)
    finally:
        if tracker is not None:
            try:
                junit_file = logger.fill_and_save(tracker)
                summary_logger.log_summary(tracker)
                summary_file = summary_logger.save_summary(tracker)
                log.info("JUnit XML:          %s", junit_file)
                log.info("Summary:            %s", summary_file)
                if log_file:
                    log.info("Log file:           %s", log_file)
                if comm_dir:
                    log.info("Communication logs: %s (%d requests)", comm_dir, comm_log.request_count())

            except Exception as e:
                log.critical("Error while saving the JUnit XML: %s", e)
                raise
