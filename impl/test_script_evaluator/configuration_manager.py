"""
Configuration manager for FHIR testing tool.
Handles loading and accessing configuration settings.
"""
import json
import os
from pathlib import Path
from utils import *

class ConfigManager:
    """
    Manages configuration loading and provides access to configuration values.

    Attributes:
        config (dict): Loaded configuration dictionary
        base_dir (Path): Base directory of the project
    """

    def __init__(self, config_path=None):
        """
        Initializes the ConfigManager and loads configuration.

        :param config_path: Optional custom path to config.json file.
                           If None, uses default location.
        """
        self.base_dir = Path(__file__).resolve().parent.parent

        if config_path is None:
            self.config_path = self.base_dir / "config.json"
        else:
            self.config_path = Path(config_path)

        self.config = self._load_config()

    def _load_config(self):
        """
        Loads configuration from config.json file.

        :return: Configuration dictionary or empty dict if not found/invalid.
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

            # in dein Log schreiben

            log_to_file(message)
        except (FileNotFoundError) as er:
            log_to_file(f"Warning: Could not load config from {self.config_path}: {er}")
            return {}

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

    def get(self, key, default=None):
        """
        Gets a configuration value by key.

        :param key: The configuration key to retrieve.
        :param default: Default value if key is not found.
        :return: The configuration value or default.
        """
        return self.config.get(key, default)

    def has_fhir_server(self):
        """
        Checks if a FHIR server is configured.

        :return: True if a FHIR server is configured, False otherwise.
        """
        return bool(self.fhir_server and self.fhir_server.strip())

    def get_testscripts_from_config(self):

        TESTSCRIPT_FOLDER = "../Test_Scripts"

        # Testscripts aus der Config ODER Ordner

        testscripts = self.config.get("testscripts", [])

        if not testscripts:
            testscripts = [
                os.path.join(TESTSCRIPT_FOLDER, name).replace("\\", "/")
                for name in os.listdir(TESTSCRIPT_FOLDER)
                if name.endswith(".json")
            ]

        result = []

        for ts_path in testscripts:

            # Testscript laden
            with open(ts_path, "r", encoding="utf-8") as ts_file:
                testscript = json.load(ts_file)

            try:
                with open(ts_path, "r", encoding="utf-8") as ts_file:
                    testscript = json.load(ts_file)


            except json.decoder.JSONDecodeError as e:

                message = (
                    "INVALID JSON\n"
                    f"File: {ts_path}\n"
                    f"Error: {e.msg}\n"
                    f"Line: {e.lineno}, Column: {e.colno}\n"
                )

                # in dein Log schreiben

                log_to_file(message)

            fixtures_raw = get_fixture(testscript)
            fixture_list = []

            for fixture in fixtures_raw:
                fixture_ref = fixture.get("resource", {}).get("reference")
                if fixture_ref:
                    filename = os.path.splitext(os.path.basename(fixture_ref))[0] + ".json"
                    fixture_path = f"Example_Instances/{filename}".replace("\\", "/")
                    fixture_list.append(fixture_path)

            ts_path_clean = ts_path.replace("../", "")
            result.append((ts_path_clean, fixture_list))

        return result


# Singleton instance for easy import
_config_manager = None


def get_config_manager(config_path=None):
    """
    Gets or creates the global ConfigManager instance.

    :param config_path: Optional custom path to config.json.
    :return: ConfigManager instance.
    """
    global _config_manager

    if _config_manager is None:
        _config_manager = ConfigManager(config_path)

    return _config_manager


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
