class Fixture:

    def __init__(self, fixture_id,source_id ,  autodelete, type,  server_id = ""):
        self.fixture_id = fixture_id     # z.B. "HL7ATCorePatientCreateTestExample"
        self.server_id = server_id           # its own local identifier
        self.source_id = source_id                #filled after Server gets initial bundle
        self.autodelete = autodelete                # should it be deleted?
        self.type = type                # for deletion

    def __repr__(self):
        return f"Fixture(example={self.fixture_id}, source={self.source_id}, server={self.server_id})"
