"""
Logging of a test run.

The runner logs through the loggers below ``testrunner`` (``testrunner.config``,
``testrunner.executor``, ``testrunner.http``, ...). Their records go to the console
and, once the configuration is loaded, to the log file of the run,
``<results>/Logs/test_run_<timestamp>.log``. The requests sent to the FHIR server are
written to ``<results>/communication_logs/test_run_<timestamp>/`` by the
``communication_logger``.

Settings in the ``logging`` object of config.json:

=========================== ======================================================== =======
``consoleLevel``            Level of the console output                              INFO
``fileLevel``               Level of the log file                                    DEBUG
``communicationLogs``       Write every request/response to ``communication_logs/``  true
``includeCommunicationInLog`` Also write every request/response into the log (DEBUG) false
=========================== ======================================================== =======
"""
import logging
import platform
import shutil
import subprocess
import sys
from pathlib import Path

import requests

import impl.test_script_evaluator.communication_logger as comm_log
from impl.test_script_evaluator.configuration_manager import ConfigManager

CONSOLE_FORMAT = "%(asctime)s %(levelname)-7s %(message)s"
CONSOLE_DATEFMT = "%H:%M:%S"
FILE_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-7s %(name)-20s %(message)s"
FILE_DATEFMT = "%Y-%m-%d %H:%M:%S"

log = logging.getLogger("testrunner")
config_log = logging.getLogger("testrunner.config")

_console_handler: logging.Handler | None = None
_file_handler: logging.Handler | None = None


def setup_console(level: int = logging.INFO) -> None:
    """
    Logs to the console. Called before the configuration is loaded, so that
    problems with the configuration are logged as well.

    :param level: Lowest level written to the console.
    """
    global _console_handler
    if _console_handler is None:
        _console_handler = logging.StreamHandler(sys.stdout)
        _console_handler.setFormatter(logging.Formatter(CONSOLE_FORMAT, CONSOLE_DATEFMT))
        root = logging.getLogger()
        root.addHandler(_console_handler)
        root.setLevel(logging.WARNING)  # libraries only get through with warnings
        logging.captureWarnings(True)
    _console_handler.setLevel(level)
    _update_logger_level()


def start_run(cm: ConfigManager, run_stamp: str) -> tuple[Path | None, Path | None]:
    """
    Sets up the logging of a test run as configured: console level, log file
    and communication logs.

    :param cm: The loaded configuration.
    :param run_stamp: Timestamp of the run, shared with the result files.
    :returns: Tuple of (log file, communication log folder); either is None if disabled
        or not writable.
    """
    global _file_handler
    problems = []
    console_level = _parse_level(cm.log_console_level, "logging.consoleLevel", logging.INFO, problems)
    file_level = _parse_level(cm.log_file_level, "logging.fileLevel", logging.DEBUG, problems)
    setup_console(console_level)

    log_file: Path | None = cm.results_dir / "Logs" / f"test_run_{run_stamp}.log"
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        _file_handler = logging.FileHandler(log_file, encoding="utf-8")
        _file_handler.setFormatter(logging.Formatter(FILE_FORMAT, FILE_DATEFMT))
        _file_handler.setLevel(file_level)
        logging.getLogger().addHandler(_file_handler)
        _update_logger_level()
    except OSError as e:
        problems.append(f"Could not open the log file {log_file}: {e}")
        log_file = None

    comm_dir = None
    if cm.communication_logs:
        comm_dir = cm.results_dir / "communication_logs" / f"test_run_{run_stamp}"
    comm_log.configure(comm_dir, cm.include_communication_in_log, cm.fhir_server or "")

    if cm.include_communication_in_log and min(console_level, file_level) > logging.DEBUG:
        problems.append("logging.includeCommunicationInLog is set, but neither consoleLevel nor "
                        "fileLevel is DEBUG, so the requests and responses are not written to the log")
    for problem in problems:
        config_log.warning(problem)
    return log_file, comm_dir


def log_configuration(cm: ConfigManager, run_stamp: str, log_file: Path | None, comm_dir: Path | None) -> None:
    """
    Writes the configuration and the environment of the run to the log and warns
    about settings that will keep TestScripts from running.

    :param cm: The loaded configuration.
    :param run_stamp: Timestamp of the run.
    :param log_file: The log file of the run, or None.
    :param comm_dir: The communication log folder of the run, or None.
    """
    path = Path(cm.path) if cm.path else None
    testscripts = cm.testscripts
    if testscripts:
        testscripts_text = f"{len(testscripts)} listed in the configuration"
    elif path:
        testscripts_text = f"all .json files in {path / 'Test_Scripts'}"
    else:
        testscripts_text = "none"

    rows = [
        ("Run", run_stamp),
        ("Config file", str(cm.config_path.resolve())),
        ("IG url", cm.url or "-"),
        ("Resource path", str(path) if path else "-"),
        ("FHIR server", cm.fhir_server or "- (TestScripts will be skipped)"),
        ("Results", str(cm.results_dir)),
        ("TestScripts", testscripts_text),
        ("Validation", _describe_validation(cm)),
        ("Log file", f"{log_file} (level {logging.getLevelName(_file_handler.level)})"
                     if log_file and _file_handler else "-"),
        ("Console level", logging.getLevelName(_console_handler.level) if _console_handler else "-"),
        ("Communication logs", str(comm_dir) if comm_dir else "disabled"),
        ("Communication in log", "yes (DEBUG)" if cm.include_communication_in_log else "no"),
    ]
    width = max(len(name) for name, _ in rows)
    config_log.info("TestFhiry TestRunner - configuration")
    for name, value in rows:
        config_log.info("  %s %s", f"{name}:".ljust(width + 1), value)

    config_log.debug("Python %s on %s, requests %s", platform.python_version(), platform.platform(),
                     requests.__version__)
    config_log.debug("Raw configuration: %s", cm.config)

    if not cm.has_fhir_server():
        config_log.warning("No FHIR server configured (fhirServer), all TestScripts will be skipped")
    if not path or not path.is_dir():
        config_log.error("Resource path '%s' is not a directory, no TestScripts can be loaded", cm.path)
    elif not cm.validator:
        jar = cm.validator_jar
        if not jar.is_file():
            config_log.warning("Validation is enabled, but %s does not exist; TestScript validation and "
                               "validateProfileId assertions will fail (run with --novalidator to skip them)", jar)


def log_testscripts(pairs: list[tuple[str, list[str], Exception | None]]) -> None:
    """
    Logs the TestScripts that will be run and the Example Instances backing their fixtures.

    :param pairs: List of ``(testscript_path, [fixture_paths...], problem)``.
    """
    config_log.info("%d TestScript(s) to run:", len(pairs))
    for index, (testscript_path, fixture_paths, problem) in enumerate(pairs, start=1):
        config_log.info("  %d. %s", index, testscript_path)
        if problem:
            config_log.warning("       cannot be loaded: %s", problem)
        for fixture_path in fixture_paths:
            config_log.debug("       fixture: %s", fixture_path)


def _describe_validation(cm: ConfigManager) -> str:
    """Validation settings, including the Java runtime the validator would be started with."""
    if cm.validator:
        return "disabled (--novalidator)"
    jar = cm.validator_jar
    jar_text = f"{jar}" if jar.is_file() else f"{jar} (MISSING)"
    return f"FHIR {cm.fhir_version}, {jar_text}, Java: {_java_version()}"


def _java_version() -> str:
    """First line of ``java -version`` for the java found on the PATH, as the validator runs it."""
    java = shutil.which("java")
    if not java:
        return "not found on PATH"
    try:
        completed = subprocess.run([java, "-version"], capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError) as e:
        return f"{java} ({type(e).__name__})"
    output = (completed.stderr or completed.stdout).decode("utf-8", errors="replace").strip()
    return f"{java} ({output.splitlines()[0] if output else 'version unknown'})"


def _parse_level(value, setting: str, default: int, problems: list[str]) -> int:
    """
    Converts a level name such as ``"info"`` into a logging level.

    :param value: The configured value, or None.
    :param setting: Name of the setting, for the warning.
    :param default: Level used when nothing or something invalid is configured.
    :param problems: Collects a warning for an invalid value.
    """
    if value is None or value == "":
        return default
    level = logging.getLevelName(str(value).upper())
    if isinstance(level, int):
        return level
    problems.append(f"{setting}: unknown level '{value}', using {logging.getLevelName(default)} "
                    f"(valid: DEBUG, INFO, WARNING, ERROR, CRITICAL)")
    return default


def _update_logger_level() -> None:
    """Lets the ``testrunner`` loggers create records down to the lowest handler level."""
    levels = [handler.level for handler in (_console_handler, _file_handler) if handler is not None]
    log.setLevel(min(levels) if levels else logging.INFO)
