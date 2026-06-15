import json
import os


class Configuration:
    """Holds runtime configuration loaded from a JSON config file.

    Provides simple property accessors for common settings used by the
    FHIR TestScript runner (server URL, base path, etc.).
    """

    def __init__(self, config_path):
        self.config_path = config_path
        self._config_data = self._load_config()

    def _load_config(self):
        """Loads and parses the JSON configuration file.

        :returns: Parsed configuration dictionary.
        :raises FileNotFoundError: If the config file does not exist.
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def server(self):
        """Gets the FHIR server base URL.

        Falls back to a default sandbox URL if not specified.
        """
        #return self._config_data.get("server", "https://hapi.fhir.org/baseR5")
        return self._config_data.get("server", "http://cql-sandbox.projekte.fh-hagenberg.at:8080/fhir")

    @property
    def url(self):
        """Gets the configured URL (often the IG base URL)."""
        return self._config_data.get("url", "")

    @property
    def path(self):
        """Gets the local filesystem path (root for resources, test scripts, etc.)."""
        return self._config_data.get("path", "")

    @property
    def output_type(self):
        """Gets the desired log/output format (txt, html, or pdf).

        Defaults to 'txt' for unknown values.
        """
        value = self._config_data.get("log_format", "txt").lower()
        if value not in ["txt", "html", "pdf"]:
            print(f"Unknown log_format '{value}', defaulting to 'txt'")
            return "txt"
        return value
