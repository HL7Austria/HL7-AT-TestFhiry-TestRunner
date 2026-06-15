from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import json
from pathlib import Path
import time

import impl.test_script_evaluator.utils as utils
import impl.test_script_evaluator.configuration_manager as conf_man

@dataclass
class TestOutcome:
    class_type: str
    name: str
    time_spent: float
    assertion_count: int
    result: str
    message: str
    error_type: Optional[str] = None

@dataclass
class TestScriptResult:
    name: str
    url: str
    outcome: str
    outcomes: List[TestOutcome] = field(default_factory=list)

@dataclass
class TestRunResults:
    timestamp: str
    testscript_results: List[TestScriptResult] = field(default_factory=list)

class ResultTracker:
    def __init__(self):
        self.current_test_run = None
        self.current_testscript = None
        self.current_outcome = None
        self._phase_start_time = None
    
    def initialize_test_run(self):
        self.current_test_run = TestRunResults(
            timestamp=datetime.now().isoformat()
        )
    
    def initialize_testscript(self, name: str, url: str):
        self.current_testscript = TestScriptResult(
            name=name, url=url, outcome="pass"
        )
        if self.current_test_run:
            self.current_test_run.testscript_results.append(self.current_testscript)
    
    def start_outcome(self, class_type: str, name: str):
        self.current_outcome = TestOutcome(
            class_type=class_type, name=name,
            time_spent=0.0, assertion_count=0,
            result="pass", message=""
        )
        self._phase_start_time = time.time()
    
    def finish_outcome(self, time_spent: float = None, result: str = None, 
                      message: str = None, error_type: Optional[str] = None):
        if self.current_outcome is None:
            return
        if time_spent is None and self._phase_start_time is not None:
            time_spent = time.time() - self._phase_start_time
        if time_spent is None:
            time_spent = 0.0
        if result is None:
            result = "pass"
        if message is None:
            message = ""
        if self.current_outcome and self.current_testscript:
            self.current_outcome.time_spent = time_spent
            self.current_outcome.result = result
            self.current_outcome.message = message
            self.current_outcome.error_type = error_type
            self.current_testscript.outcomes.append(self.current_outcome)
            if result == "fail":
                self.current_testscript.outcome = "fail"
            self.current_outcome = None
            self._phase_start_time = None
    
    def increment_assertion_count(self):
        if self.current_outcome:
            self.current_outcome.assertion_count += 1

    def set_assertion_count(self, count):
        if self.current_outcome:
            self.current_outcome.assertion_count = count

    def save_results(self):
        if not self.current_test_run:
            return None
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
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"test_results_{timestamp}.json"
        filepath = Path(results_dir) / filename
        results_dict = {
            "timestamp": self.current_test_run.timestamp,
            "testscript_results": []
        }
        for ts in self.current_test_run.testscript_results:
            ts_dict = {
                "name": ts.name,
                "url": ts.url,
                "outcome": ts.outcome,
                "outcomes": []
            }
            for outcome in ts.outcomes:
                outcome_dict = {
                    "class": outcome.class_type,
                    "name": outcome.name,
                    "time_spent": outcome.time_spent,
                    "assertion_count": outcome.assertion_count,
                    "result": outcome.result,
                    "message": outcome.message,
                    "error_type": outcome.error_type
                }
                ts_dict["outcomes"].append(outcome_dict)
            results_dict["testscript_results"].append(ts_dict)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results_dict, f, indent=2)
        return filepath
    
    def emit_summary_to_log(self):
        if not self.current_test_run:
            return
        utils.log_to_file("\n=========== Test Run Summary ===========")
        for ts in self.current_test_run.testscript_results:
            utils.log_to_file(f"TestScript: {ts.name} - {ts.outcome}")
            for o in ts.outcomes:
                utils.log_to_file(f"  {o.class_type} [{o.name}]: {o.result} ({o.time_spent:.3f}s, {o.assertion_count} assertions)")
                if o.message:
                    utils.log_to_file(f"    message: {o.message}")
        utils.log_to_file("======================================\n")

_result_tracker = None

def get_result_tracker():
    global _result_tracker
    if _result_tracker is None:
        _result_tracker = ResultTracker()
    return _result_tracker

def init_result_tracker():
    global _result_tracker
    _result_tracker = ResultTracker()
    return _result_tracker

def reset_result_tracker():
    global _result_tracker
    if _result_tracker is not None:
        _result_tracker.current_test_run = None
        _result_tracker.current_testscript = None
        _result_tracker.current_outcome = None
        _result_tracker._phase_start_time = None
