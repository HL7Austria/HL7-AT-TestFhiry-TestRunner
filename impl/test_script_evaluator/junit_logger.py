from impl.test_script_evaluator.result_tracker import ResultTracker
from junitparser import TestCase, TestSuite, JUnitXml, Skipped, Error, Failure
from datetime import datetime
from pathlib import Path
from xml.dom.minidom import parseString
import impl.test_script_evaluator.configuration_manager as conf_man
def construct_junit(tracker: ResultTracker) -> JUnitXml:
    """
    Constructs the Body of a JUnit style xml from a ResultTracker object.
    The XML is a very basic Junit style xml as any added info is simply ignored.

    :param tracker: filled Resulttracker
    
    :raises Exception: If the tracker is empty
    """
    if not tracker:
        raise Exception("tracker needs to be filled before saving as Junit XML")
    
    res_junit = JUnitXml()
    res_junit.time = tracker.current_test_run.total_time
    for testscrpt in tracker.current_test_run.testscript_results:
        suite = TestSuite(testscrpt.name)
        suite.classname = "TestScript"
        suite.time = testscrpt.total_time
        for phase in testscrpt.outcomes:
            case = TestCase(phase.name)
            case.classname = phase.class_type
            case.assertions = phase.assertion_count
            case.time = phase.time_spent

            first_msg = phase.message[0] if phase.message else ""
            extra_msgs = phase.message[1:]
            if phase.result == "fail":
                if phase.error_type == "TestScriptError":
                    case.result = [Error(message=first_msg, type_=phase.error_type)]
                else:
                    case.result = [Failure(message=first_msg, type_=phase.error_type)]
                if extra_msgs:
                    case.result[0]._elem.text = "\n".join(extra_msgs)
            elif phase.result == "skip":
                case.result = [Skipped(message=first_msg)]
            else:
                case.system_out = "\n".join(phase.message) if phase.message else ""
            suite.add_testcase(case)
        res_junit.add_testsuite(suite)
    return res_junit

def fill_and_save(tracker: ResultTracker):
    results_dir = None
    cm = conf_man.get_config_manager()
    if cm is not None and getattr(cm, "results_path", None):
        results_dir = cm.results_path

    if cm is not None:
        if getattr(cm, "results_path", None):
            results_dir = cm.results_path
        elif getattr(cm, "path", None):
            results_dir = Path(cm.path) / "Result"
        else:
            base = Path(__file__).resolve().parent.parent
            results_dir = base / "Results"
    
    junit_dir = Path(results_dir) / "Junit"
    junit_dir.mkdir(parents=True, exist_ok=True)
    filename = f"test_results_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xml"
    filepath = junit_dir / filename
    junit = construct_junit(tracker)
    
    save_xml(junit, str(filepath))

def save_xml(body: JUnitXml, filepath: str):
    """saves xml file with body as content"""

    if not filepath.endswith(".xml"):
         filepath += ".xml"
    try:
        body.write(filepath, pretty=True)
    except Exception as e:
        raise Exception("Junit File could not be saved correctly!")
