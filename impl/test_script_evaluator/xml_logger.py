from impl.test_script_evaluator.result_tracker import ResultTracker
from bs4 import BeautifulSoup
from impl.test_script_evaluator.utils import string_type
from datetime import datetime
from pathlib import Path
from xml.dom.minidom import parseString
import impl.test_script_evaluator.configuration_manager as conf_man
def construct_body(tracker: ResultTracker) -> str:
    """
    Constructs the Body of a JUnit style xml from a ResultTracker object.
    The XML is a very basic Junit style xml as any added info is simply ignored.

    :param tracker: filled Resulttracker
    
    :raises Exception: If the tracker is empty
    """
    if not tracker:
        raise Exception("tracker needs to be filled before saving as Junit XML")
    result = f"""<?xml version="1.0" encoding="UTF-8"?>
    <testsuites time="{tracker.current_test_run.total_time}">"""
    for testscrpt in tracker.current_test_run.testscript_results:
        result += f"""<testsuit name="{testscrpt.name}" classname="TestScript" time="{testscrpt.total_time}">"""
        for phase in testscrpt.outcomes:
            result += f"""<testcase name="{phase.name}" classname="{phase.class_type}" assertions="{phase.assertion_count}" time="{phase.time_spent}">"""
            first_msg = phase.message[0] if phase.message else ""
            extra_msgs = phase.message[1:]
            if phase.result == "fail":
                tag = "error" if phase.error_type == "TestScriptError" else "failure"
                if extra_msgs:
                    result += f"""<{tag} message="{first_msg}" type="{phase.error_type}">"""
                    result += f"""<system-out>{chr(10).join(extra_msgs)}</system-out>"""
                    result += f"""</{tag}>"""
                else:
                    result += f"""<{tag} message="{first_msg}" type="{phase.error_type}"/>"""
            elif phase.result == "skip":
                result += f"""<skipped message="{first_msg}"/>"""
            else:
                result += f"""<system-out>{chr(10).join(phase.message)}</system-out>"""
            result += "</testcase>"
        result +="</testsuit> "
    result+="</testsuites>"
    return result

def fill_and_save(tracker: ResultTracker):
    results_dir = None
    try:
        cm = conf_man.get_config_manager()
        if cm is not None and getattr(cm, "results_dir", None):
            results_dir = cm.results_dir
    except Exception:
        pass
    if results_dir is None:
        base = Path(__file__).resolve().parent.parent
        results_dir = base / "Results"
        results_dir.mkdir(parents=True, exist_ok=True)
    filename = f"test_results_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xml"
    filepath = Path(results_dir) / filename
    body = construct_body(tracker)
    pretty_body = parseString(body.encode("utf-8")).toprettyxml(indent="    ", encoding="UTF-8").decode("utf-8")
    save_xml(pretty_body, str(filepath))

def save_xml(body: str, filepath: str):
    """saves xml file with body as content"""

    if not filepath.endswith(".xml"):
         filepath += ".xml"
    try:
        with open(filepath, "w", encoding="utf-8") as f:
               f.write(body)
    except Exception as e:
        raise
