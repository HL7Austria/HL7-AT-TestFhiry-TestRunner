from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime
import json
from pathlib import Path
import time
from dataclasses import asdict

import impl.test_script_evaluator.utils as utils
import impl.test_script_evaluator.configuration_manager as conf_man
import impl.exception.Error as error

@dataclass
class TestOutcome:
    """Represents the outcome of a single phase (Setup, Test, or Teardown) within a TestScript run.

    Captures timing, assertion counts, pass/fail result, any message, and optional
    error classification for later reporting and persistence.
    """
    class_type: str
    name: str
    time_spent: float
    assertion_count: int
    result: str
    message: List[str]
    error_type: Optional[str] = None

@dataclass
class TestScriptResult:
    """Aggregates results for a single TestScript execution.

    Contains overall outcome and a list of per-phase outcomes (Setup/Test/Teardown).
    """
    name: str
    url: str
    outcome: str
    timestamp: str = ""
    total_time: float = 0.0
    outcomes: List[TestOutcome] = field(default_factory=list)

@dataclass
class TestRunResults:
    """Top-level container for an entire test run.

    Holds the run timestamp and a list of per-TestScript results.
    """
    timestamp: str
    total_time: float = 0.0
    testscript_results: List[TestScriptResult] = field(default_factory=list)

class ResultTracker:
    """Tracks execution results across a full test run of one or more TestScripts.

    Maintains mutable state for the current run, the current TestScript, and the
    active phase outcome. Provides methods to initialize, record, and persist
    structured results, as well as emit a human-readable summary to the log.
    """

    def __init__(self):
        self.current_test_run = None
        self.current_testscript = None
        self.current_outcome = None
        self._phase_start_time = None
    
    def initialize_test_run(self):
        """Starts a new overall test run, resetting the current run container with a timestamp."""
        self.current_test_run = TestRunResults(
            timestamp=datetime.now().isoformat()
        )
    
    def initialize_testscript(self, name: str, url: str):
        """Begins tracking results for a single TestScript.

        Creates a TestScriptResult and attaches it to the current run (if any).

        :param name: Human-readable name of the TestScript.
        :param url: Source path or URL of the TestScript.
        """
        self.current_testscript = TestScriptResult(
            name=name, url=url, outcome="pass", timestamp=datetime.now().isoformat()
        )
        if self.current_test_run:
            self.current_test_run.testscript_results.append(self.current_testscript)
    
    def start_outcome(self, class_type: str, name: str):
        """Starts timing and tracking a new phase outcome (e.g. Setup, a named Test, or Teardown).

        :param class_type: Category label (e.g. 'Setup', 'Test', 'Teardown').
        :param name: Specific name for the phase (often the test name or 'Setup'/'Teardown').
        """
        self.current_outcome = TestOutcome(
            class_type=class_type, name=name,
            time_spent=0.0, assertion_count=0,
            result="pass", message=""
        )
        self._phase_start_time = time.time()
    
    def finish_outcome(self, time_spent: float = None, result: str = None, 
                      message: str = None, error_type: Optional[str] = None):
        """Finalizes the current phase outcome, records it under the current TestScript, and clears it.

        If time/result/message/error_type are not provided, sensible defaults are used
        (elapsed time since start_outcome, 'pass', empty message, None).

        :param time_spent: Optional explicit duration in seconds.
        :param result: Optional result string ('pass' or 'fail').
        :param message: Optional descriptive message or error text.
        :param error_type: Optional classification of any error (e.g. exception class name).
        """
        if self.current_outcome is None:
            return
        if time_spent is None and self._phase_start_time is not None:
            time_spent = time.time() - self._phase_start_time
        if time_spent is None:
            time_spent = 0.0
        if result is None:
            result = "pass"
        if message is None:
            message = []
        if self.current_outcome and self.current_testscript:
            self.current_outcome.time_spent = time_spent
            self.current_outcome.result = result
            self.current_outcome.message = message
            self.current_outcome.error_type = error_type
            self.current_testscript.outcomes.append(self.current_outcome)
            self.current_testscript.total_time += time_spent
            if self.current_test_run:
                self.current_test_run.total_time += time_spent
            if result == "fail":
                self.current_testscript.outcome = "fail"
            elif result == "skip" and self.current_testscript.outcome != "fail":
                self.current_testscript.outcome = "skip"
            self.current_outcome = None
            self._phase_start_time = None
    
    def increment_assertion_count(self):
        """Increments the assertion counter on the current phase outcome, if any."""
        if self.current_outcome:
            self.current_outcome.assertion_count += 1

    def set_assertion_count(self, count):
        """Sets an explicit assertion count on the current phase outcome, if any.

        :param count: The number of assertions declared or executed in the phase.
        """
        if self.current_outcome:
            self.current_outcome.assertion_count = count

    def save_results(self):
        """Persists the current test run results to a timestamped JSON file.

        The output directory is taken from ConfigManager.results_dir if available;
        otherwise a local 'Results' directory next to the package is used/created.

        :returns: The Path to the written JSON file, or None if there is no current run.
        """
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
        filename = f"test_results_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.json"
        filepath = Path(results_dir) / filename
        results_dict = asdict(self.current_test_run)
        results_dict["testscript_results"] = []  # wird später gefüllt
        for ts in self.current_test_run.testscript_results:
            ts_dict = asdict(ts)
            ts_dict["outcomes"] = []  # wird später gefüllt
            for outcome in ts.outcomes: 
                outcome_dict = asdict(outcome)
                ts_dict["outcomes"].append(outcome_dict)
            results_dict["testscript_results"].append(ts_dict)
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(results_dict, f, indent=2)
        except PermissionError:
            raise error.TestScriptError(f"No write permission for results file: {filepath}")
        except Exception as e:
            raise error.TestScriptError(f"Failed to write results file: {filepath} - {e}")
    

_result_tracker = None

def get_result_tracker():
    """Returns the global singleton ResultTracker instance, creating it if necessary."""
    global _result_tracker
    if _result_tracker is None:
        _result_tracker = ResultTracker()
    return _result_tracker

def init_result_tracker():
    """Re-initializes and returns a fresh global ResultTracker singleton."""
    global _result_tracker
    _result_tracker = ResultTracker()
    return _result_tracker

def reset_result_tracker():
    """Clears all state on the global ResultTracker (if it exists) without replacing the instance."""
    global _result_tracker
    if _result_tracker is not None:
        _result_tracker.current_test_run = None
        _result_tracker.current_testscript = None
        _result_tracker.current_outcome = None
        _result_tracker._phase_start_time = None
