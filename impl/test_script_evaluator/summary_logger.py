from datetime import datetime
from pathlib import Path

from impl.test_script_evaluator.result_tracker import ResultTracker
import impl.test_script_evaluator.configuration_manager as conf_man

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
    skipped_scripts = sum(1 for ts in run.testscript_results if ts.outcome == "skip")
    
    lines.append(f"Total TestScripts: {total_scripts}")
    lines.append(f"passed: {passed_scripts}")
    lines.append(f"failed: {failed_scripts}")
    lines.append(f"skipped: {skipped_scripts}")
    lines.append("-" * 34)
    lines.append("-" * 34)
    
    if failed_scripts > 0:
        lines.append("failed TestScripts:")
        for ts in run.testscript_results:
            if ts.outcome == "fail":
                lines.append(ts.name)
    
    return "\n".join(lines)


def print_summary(tracker: ResultTracker):
    """
    Prints the test summary to console.

    :param tracker: filled ResultTracker
    """
    summary = format_summary(tracker)
    print(summary)

def save_summary(tracker: ResultTracker):
    """
    Saves the test summary to a text file.

    The file is saved in the Txt-files subdirectory of the results path,
    with a timestamp-based filename.

    :param tracker: filled ResultTracker
    :raises Exception: if the file could not be saved correctly
    """
    summary = format_summary(tracker) # summary str

    cm = conf_man.get_config_manager()
    
    if getattr(cm, "results_path", None):
        results_dir = cm.results_path
    elif getattr(cm, "path", None):
        results_dir = Path(cm.path) / "Result"
    else:
        base = Path(__file__).resolve().parent.parent
        results_dir = base / "Results"

    txt_dir = Path(results_dir) / "Txt-files"
    txt_dir.mkdir(parents=True, exist_ok=True)
    filename = f"test_results_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"
    filepath = txt_dir / filename

    try:
        filepath.write_text(summary)
    except Exception as e:
        raise Exception("Txt File could not be saved correctly!")



