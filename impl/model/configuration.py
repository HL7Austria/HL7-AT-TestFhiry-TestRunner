import json
import os


class Configuration:
    def __init__(self, config_path):
        self.config_path = config_path
        self._config_data = self._load_config()

    def _load_config(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    @property
    def server(self):
        return self._config_data.get("server", "https://hapi.fhir.org/baseR5")

    @property
    def url(self):
        return self._config_data.get("url", "")

    @property
    def path(self):
        return self._config_data.get("path", "")

    @property
    def output_type(self):
        value = self._config_data.get("log_format", "txt").lower()
        if value not in ["txt", "html", "pdf"]:
            print(f"Unknown log_format '{value}', defaulting to 'txt'")
            return "txt"
        return value
