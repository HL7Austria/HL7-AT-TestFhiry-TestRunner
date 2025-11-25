class Fixture:
    def __init__(self, example_path, source_id):
        self.example_path = example_path     # z.B. "Example_Instances/Patient-01.json"
        self.source_id = source_id           # dein eigener lokaler Identifier
        self.server_id = ""                 # wird gefüllt nachdem der Server das Bundle verarbeitet

    def __repr__(self):
        return f"Fixture(example={self.example_path}, source={self.source_id}, server={self.server_id})"
