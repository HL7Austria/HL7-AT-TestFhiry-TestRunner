class Fixture:
    def __init__(self, example_path, server_id, source_id = ""):
        self.example_path = example_path     # z.B. "Example_Instances/Patient-01.json"
        self.server_id = server_id           # dein eigener lokaler Identifier
        self.source_id = source_id                # wird gefüllt nachdem der Server das Bundle verarbeitet

    def __repr__(self):
        return f"Fixture(example={self.example_path}, source={self.source_id}, server={self.server_id})"
