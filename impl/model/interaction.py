class Interaction:
    """Represents a single HTTP interaction (request/response) with a FHIR server.

    Captures headers, body, status code, reason phrase, an optional
    responseId for later reference in TestScript assertions or operations,
    and the ID of the request in the communication log.
    """

    def __init__(self , header, interaction, status_code: int | str = "", res_id: str | None = "", reason = "",
                 request_id: str | None = None):

        self.header = header            # header of interaction
        self.body = interaction  # Body of interaction
        self.status_code = status_code  # status code
        self.reason = reason
        self.res_id = res_id
        self.request_id = request_id    # e.g. "REQ-0003", names the exchange in the communication log

    def __repr__(self):
        return f"Interaction(id = {self.res_id}, request = {self.request_id}, status = {self.status_code}, header = {self.header}, body = {self.body})"
