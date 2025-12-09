class Fixture:

    def __init__(self, fixture_id,source_id , server_id = ""):
        self.fixture_id = fixture_id     # z.B. "HL7ATCorePatientCreateTestExample"
        self.server_id = server_id           # dein eigener lokaler Identifier
        self.source_id = source_id                # wird gefüllt nachdem der Server das Bundle verarbeitet

    def __repr__(self):
        return f"Fixture(example={self.fixture_id}, source={self.source_id}, server={self.server_id})"
