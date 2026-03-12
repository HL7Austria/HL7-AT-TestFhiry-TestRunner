class Interaction:

    def __init__(self, response, res_id = ""):
        self.response_id = res_id   
        self.response = response

    def __repr__(self):
        return f"Response( id = {self.response_id}, {self.response.text})"
