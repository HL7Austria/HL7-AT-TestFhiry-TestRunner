class Interaction:

    def __init__(self,direction , header, interaction,status_code = "", res_id = ""):
        self.direction = direction      # response or request (could also rename to type)
        self.header = header            # header of interaction
        self.body = interaction  # Body of interaction
        self.status_code = status_code  # just trying new things
        self.res_id = res_id

    def __repr__(self):
        return f"Interaction {self.direction} = ( id = {self.res_id}, header = {self.header}, body = {self.body})"
