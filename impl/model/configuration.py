import json


class Configuration:
    def __init__(self, server, url, path, output_type):
        self.server = server
        self.url = url
        self.path = path
        self.output_type = output_type

    def _load_config(self):
        with open(self.config_path, "r") as f:
            return json.load(f)

    @property
    def url(self):
        return self.url

    @property
    def server(self):
        return self.server

    @property
    def path(self):
        return self.path

    @property
    def output_type(self):
        return self.output_type
