import json
import os
from pathlib import Path
import impl.test_script_evaluator.utils as utils

def fixture_basename_candidates(reference: str) -> list[str]:
    """Derives the possible Example Instance file stems for a fixture reference.

    Two spellings occur in practice and both must resolve:

    * the IG publisher page name, ``Patient-HL7ATCorePatientExample.html``
    * an R4 relative reference, ``Patient/HL7ATCorePatientExample``, which is what
      SUSHI emits for ``* fixture.resource = Reference(HL7ATCorePatientExample)``

    Example Instance files are named ``<ResourceType>-<id>``, so a relative reference
    has to be rejoined with a dash rather than treated as a directory.

    :param reference: The value of ``fixture.resource.reference``.
    :returns: Candidate file stems, most specific first, without extension.
    """
    segments = [seg for seg in reference.split("/") if seg]
    if not segments:
        return []

    stem = os.path.splitext(segments[-1])[0]
    candidates = []

    # "Patient/Foo" (or ".../fhir/Patient/Foo") -> "Patient-Foo"
    if len(segments) >= 2:
        candidates.append(f"{segments[-2]}-{stem}")

    # "Patient-Foo.html" -> "Patient-Foo"; also the bare-id fallback for the case above
    if stem not in candidates:
        candidates.append(stem)

    return candidates


class ConfigManager:
    """
    Manages configuration loading and provides access to configuration values.

    Attributes:
        config (dict): Loaded configuration dictionary
    """

    def __init__(self, config_path, noval):
        """
        Initializes the ConfigManager and loads configuration.

        :param config_path: Path to config.json file.
        """
        self.config_path = Path(config_path)
        self._validator = noval
        self.config = self._load_config()
        print(self.config)
        

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
    def fhir_version(self):
        """
        Gets the FHIR version the HL7 Validator CLI should validate against.

        Without it the validator falls back to its newest supported version,
        which reports R4 resources as invalid (e.g. TestScript.profile is a
        Reference in R4 but a canonical in R5).

        :return: FHIR version string from ``validation.fhirVersion``, defaults to "4.0".
        """
        return self.config.get("validation", {}).get("fhirVersion", "4.0")

    @property
    def validator(self) -> bool:
        """
        Get the decision wether validator should be used.
        
        :return: decision for validator
        """
        return self._validator

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

    def has_fhir_server(self):
        """
        Checks if a FHIR server is configured.

        :return: True if a FHIR server is configured, False otherwise.
        """
        return bool(self.fhir_server and self.fhir_server.strip())

    def get_testscripts_from_config(self):
        """Discovers TestScript files and their associated Example Instance resources.

        Uses either the explicit ``testscripts`` list from config.json or scans
        the ``Test_Scripts`` folder under the configured ``path``. For each
        TestScript, referenced fixtures are resolved to local Example Instance
        file paths (JSON or XML).

        :returns: List of tuples ``(testscript_path, [fixture_paths...])``.
        """

        if not self.path or not Path(self.path).is_dir():
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
                        fixture_path = None
                        tried = []
                        for base_name in fixture_basename_candidates(fixture_ref):
                            for ext in [".json", ".xml"]:
                                candidate = f"Example_Instances/{base_name}{ext}".replace("\\", "/")
                                tried.append(candidate)
                                if os.path.exists(utils.get_full_path(candidate)):
                                    fixture_path = candidate
                                    break
                            if fixture_path:
                                break
                        if not fixture_path:
                            # Must not be skipped: save_fixtures zips the loaded resources
                            # against the full fixture list, so a dropped entry shifts every
                            # later fixture onto the wrong body.
                            raise Exception(
                                f"No Example Instance found for fixture "
                                f"'{fixture.get('id', '<no id>')}' referencing '{fixture_ref}' "
                                f"in {ts_path}.\nTried: " + ", ".join(tried)
                            )
                        fixture_list.append(fixture_path)

                result.append((ts_path, fixture_list))

            except FileNotFoundError:
                raise
            except json.decoder.JSONDecodeError as e:
                message = (
                    "INVALID JSON\n"
                    f"File: {ts_path}\n"
                    f"Error: {e.msg}\n"
                    f"Line: {e.lineno}, Column: {e.colno}\n"
                )
                raise json.decoder.JSONDecodeError(message)


        if not result:
            raise FileExistsError("No valid TestScripts found!")
        return result
# Singleton instance for easy import
_config_manager = None


def get_config_manager() -> ConfigManager:
    """
    Gets global ConfigManager instance.
    :return: ConfigManager instance.
    """
    assert _config_manager is not None
    return _config_manager

def init_config_manager(config_path: str, noval: bool):
    """Initializes the global ConfigManager instance."""
    global _config_manager
    _config_manager = ConfigManager(config_path, noval)



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


def get_validator():
    """Convenience function to get validator setting."""
    return get_config_manager().validator


def get_fhir_version():
    """Convenience function to get the FHIR version for the validator."""
    return get_config_manager().fhir_version

