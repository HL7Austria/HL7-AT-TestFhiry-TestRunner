class Fixture:

    def __init__(self, fixture_id,source_id ,autocreate,  autodelete, type, fix_body, server_id = ""):
        self.fixture_id = fixture_id                # z.B. "HL7ATCorePatientCreateTestExample"
        self.server_id = server_id                  # filled after Server gets initial bundle
        self.source_id = source_id                  # its own local identifier
        self.autodelete = autodelete                # should it be deleted?
        self.autocreate = autocreate                # should it be created?
        self.body = fix_body
        self.type = type                            # for deletion
        self.references = []                        # List of referenced fixture_ids
        self.references_resolved = False            # Track if all references are solved
        self.original_body = fix_body               # Preserve original body with placeholder references

    def __repr__(self):
        return f"Fixture(example={self.fixture_id}, source={self.source_id}, server={self.server_id})"
