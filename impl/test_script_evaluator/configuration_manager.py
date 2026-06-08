"""
Configuration manager for FHIR testing tool.
Handles loading and accessing configuration settings.
"""
import json
import os
from datetime import datetime
from pathlib import Path
import impl.test_script_evaluator.utils as utils

class ConfigManager:
    """
    Manages configuration loading and provides access to configuration values.

    Attributes:
        config (dict): Loaded configuration dictionary
    """

    def __init__(self, config_path):
        """
        Initializes the ConfigManager and loads configuration.

        :param config_path: Path to config.json file.
        """
        self.config_path = Path(config_path)

        self.config = self._load_config()
        self._results_dir = None
        self._log_file_path = None

    def _load_config(self):
        """
        Loads configuration from config.json file.

        :return: Configuration dictionary.
        :raises: json.decoder.JSONDecodeError if config.json is malformed.
        :raises: FileNotFoundError if config.json does not exist.
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)

        except json.decoder.JSONDecodeError as e:
            message = (
                "INVALID JSON\n"
                f"File: {self.config_path}\n"
                f"Error: {e.msg}\n"
                f"Line: {e.lineno}, Column: {e.colno}\n"
            )
            raise Exception(message)
        except FileNotFoundError as er:
            message = f"Config file not found: {self.config_path}"
            raise Exception(message)
        

    @property
    def fhir_server(self):
        """
        Gets the FHIR server URL from configuration.

        :return: FHIR server URL or None if not configured.
        """
        return self.config.get("fhirServer")

    @property
    def url(self):
        """
        Gets the URL from configuration.

        :return: URL string or empty string if not configured.
        """
        return self.config.get("url", "")

    @property
    def path(self):
        """
        Gets the path from configuration.

        :return: Path string or empty string if not configured.
        """
        return self.config.get("path", "")

    @property
    def testscripts(self):
        """
        Gets the list of testscripts from configuration.

        :return: List of testscript paths or empty list if not configured.
        """
        return self.config.get("testscripts", [])

    @property
    def results_path(self):
        """
        Gets the results_path from configuration.

        :return: results_path string or empty string if not configured.
        """
        return self.config.get("results_path", "")

    def get(self, key, default=None):
        """
        Gets a configuration value by key.

        :param key: The configuration key to retrieve.
        :param default: Default value if key is not found.
        :return: The configuration value or default.
        """
        return self.config.get(key, default)

    @property
    def results_dir(self):
        """
        Gets the Results directory path (parent of config path).

        :return: Path to the Results directory.
        """
        return self._results_dir

    @property
    def log_file_path(self):
        """
        Gets the log file path inside the Results directory.

        :return: Absolute path string to the log file.
        """
        return self._log_file_path

    def init_logging(self):
        """
        Initializes the Results directory and log file based on config path.
        Creates the directory and an initial log file.
        """
        if self.results_path:
            self._results_dir = Path(self.results_path) / "Results"
        else:
            self._results_dir = Path(self.path) / "Results"
        self._results_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_filename = f"test_results_{timestamp}.txt"
        self._log_file_path = os.path.abspath(self._results_dir / log_filename)
        with open(self._log_file_path, "w", encoding="utf-8") as f:
            f.write(f"FHIR Test Log - {datetime.now()}\n\n")

    def has_fhir_server(self):
        """
        Checks if a FHIR server is configured.

        :return: True if a FHIR server is configured, False otherwise.
        """
        return bool(self.fhir_server and self.fhir_server.strip())

    def get_testscripts_from_config(self):

        if not self.path or not Path(self.path).is_dir():
            utils.log_to_file(f"Test konnte nicht gestartet werden: 'path' ist leer oder existiert nicht ({self.path!r})")
            return []

        TESTSCRIPT_FOLDER = str(Path(self.path) / "Test_Scripts")

        # Testscripts aus der Config ODER Ordner

        testscripts_raw = self.config.get("testscripts", [])
        testscripts = [
            str(Path(self.path) / ts).replace("\\", "/") if not Path(ts).is_absolute() else ts
            for ts in testscripts_raw
        ]

        if not testscripts:
            testscripts = [
                os.path.join(TESTSCRIPT_FOLDER, name).replace("\\", "/")
                for name in os.listdir(TESTSCRIPT_FOLDER)
                if name.endswith(".json")
            ]

        result = []

        for ts_path in testscripts:
            try:
                with open(ts_path, "r", encoding="utf-8") as ts_file:
                    testscript = json.load(ts_file)

                fixtures_raw = utils.get_fixture(testscript)
                fixture_list = []

                for fixture in fixtures_raw:
                    fixture_ref = fixture.get("resource", {}).get("reference")
                    if fixture_ref:
                        filename = os.path.splitext(os.path.basename(fixture_ref))[0] + ".json"
                        fixture_path = str(Path(self.path) / "Example_Instances" / filename).replace("\\", "/")
                        fixture_list.append(fixture_path)

                result.append((ts_path, fixture_list))

            except FileNotFoundError:
                utils.log_to_file(f"TestScript not found: {ts_path}")
            except json.decoder.JSONDecodeError as e:

                message = (
                    "INVALID JSON\n"
                    f"File: {ts_path}\n"
                    f"Error: {e.msg}\n"
                    f"Line: {e.lineno}, Column: {e.colno}\n"
                )

                utils.log_to_file(message)

            fixtures_raw = utils.get_fixture(testscript)
            fixture_list = []

            for fixture in fixtures_raw:
                fixture_ref = fixture.get("resource", {}).get("reference")
                if fixture_ref:
                    base_name = os.path.splitext(os.path.basename(fixture_ref))[0]
                    fixture_path = None
                    for ext in [".json", ".xml"]:
                        candidate = f"Example_Instances/{base_name}{ext}".replace("\\", "/")
                        if os.path.exists(utils.get_full_path(candidate)):
                            fixture_path = candidate
                            break
                    if fixture_path:
                        fixture_list.append(fixture_path)
                    else:
                        utils.log_to_file(f"Warning: Example Instance not found for {base_name} (.json or .xml)")

            ts_path_clean = ts_path.replace("../", "")
            result.append((ts_path_clean, fixture_list))
        if not result:
            utils.log_to_file("No valid TestScripts found")

        return result


# Singleton instance for easy import
_config_manager = None


def get_config_manager() -> ConfigManager:
    """
    Gets global ConfigManager instance.
    :return: ConfigManager instance.
    """
    return _config_manager

def init_config_manager(config_path):
    """Initializes the global ConfigManager instance."""
    global _config_manager
    _config_manager = ConfigManager(config_path)


# Convenience functions for direct access
def get_fhir_server():
    """Convenience function to get FHIR server URL."""
    return get_config_manager().fhir_server


def get_testscript_pairs():
    """Convenience function to get testscript pairs."""
    return get_config_manager().get_testscripts_from_config()


def has_fhir_server():
    """Convenience function to check if FHIR server is configured."""
    return get_config_manager().has_fhir_server()
