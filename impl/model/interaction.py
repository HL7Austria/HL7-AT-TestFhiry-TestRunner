class Interaction:

    def __init__(self,direction , header, interaction, res_id = ""):
        self.direction = direction      # response or request (could also rename to type)
        self.header = header            # header of interaction
        self.interaction = interaction  # Body of interaction
        self.res_id = res_id

    def __repr__(self):
        return f"Interaction {self.direction} = ( id = {self.res_id}, {self.interaction})"
