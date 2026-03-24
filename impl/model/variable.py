class Variable:
    def __init__(self, name : str, path=None, expression=None, headerField=None, defaultValue=None,sourceId=None):
        self.name = name
        self.path = path
        self.expression = expression
        self.headerField = headerField
        self.defaultValue = defaultValue
        self.sourceId = sourceId
        