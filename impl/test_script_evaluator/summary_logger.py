import logging
from pathlib import Path

from impl.test_script_evaluator.result_tracker import ResultTracker
import impl.test_script_evaluator.configuration_manager as conf_man

log = logging.getLogger("testrunner.summary")

def format_summary(tracker: ResultTracker) -> str:
    """
    Formats a human-readable summary from the ResultTracker data.

    :param tracker: filled ResultTracker
    :return: Formatted summary string
    """
    if not tracker or not tracker.current_test_run:
        return "No test results available."
    
    run = tracker.current_test_run
    lines = []
    
    total_scripts = len(run.testscript_results)
    passed_scripts = sum(1 for ts in run.testscript_results if ts.outcome == "pass")
    failed_scripts = sum(1 for ts in run.testscript_results if ts.outcome == "fail")
    error_scripts = sum(1 for ts in run.testscript_results if ts.outcome == "error")
    skipped_scripts = sum(1 for ts in run.testscript_results if ts.outcome == "skip")

    lines.append(f"Total TestScripts: {total_scripts}")
    lines.append(f"passed: {passed_scripts}")
    lines.append(f"failed: {failed_scripts}")
    lines.append(f"errors: {error_scripts}")
    lines.append(f"skipped: {skipped_scripts}")
    lines.append("-" * 34)

    if failed_scripts > 0:
        lines.append("failed TestScripts:")
        for ts in run.testscript_results:
            if ts.outcome == "fail":
                lines.append(ts.name)

    if error_scripts > 0:
        lines.append("TestScripts with errors (TestScript or tool could not be executed):")
        for ts in run.testscript_results:
            if ts.outcome == "error":
                lines.append(ts.name)

    return "\n".join(lines)


def log_summary(tracker: ResultTracker):
    """
    Writes the test summary to the log (console and log file).

    :param tracker: filled ResultTracker
    """
    log.info("===== Summary")
    for line in format_summary(tracker).splitlines():
        log.info("%s", line)

def save_summary(tracker: ResultTracker) -> Path:
    """
    Saves the test summary to a text file.

    The file is saved in the Txt-files subdirectory of the results path,
    with a timestamp-based filename.

    :param tracker: filled ResultTracker
    :return: Path of the written file
    :raises Exception: if the file could not be saved correctly
    """
    summary = format_summary(tracker) # summary str

    txt_dir = conf_man.get_config_manager().results_dir / "Txt-files"
    txt_dir.mkdir(parents=True, exist_ok=True)
    filename = f"test_results_{tracker.run_file_stamp()}.txt"
    filepath = txt_dir / filename

    try:
        filepath.write_text(summary)
    except Exception as e:
        raise Exception("Txt File could not be saved correctly!")
    return filepath



