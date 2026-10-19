class Interaction:
    """Represents a single HTTP interaction (request/response) with a FHIR server.

    Captures headers, body, status code, reason phrase, and an optional
    responseId for later reference in TestScript assertions or operations.
    """

    def __init__(self , header, interaction, status_code: int | str = "", res_id: str | None = "", reason = ""):

        self.header = header            # header of interaction
        self.body = interaction  # Body of interaction
        self.status_code = status_code  # status code
        self.reason = reason
        self.res_id = res_id

    def __repr__(self):
        return f"Interaction(id = {self.res_id}, status = {self.status_code}, header = {self.header}, body = {self.body})"
