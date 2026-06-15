class Variable:
    """Represents a FHIR TestScript variable definition.
        
    A variable can obtain its value from a FHIRPath expression, a path,
    a header field, or a default value. Exactly one value source (or
    defaultValue) must be provided.
    """

    def __init__(self, name : str, path=None, expression=None, headerField=None, defaultValue=None,sourceId=None):
        self.name = name
        self.path = path
        self.expression = expression
        self.headerField = headerField
        self.defaultValue = defaultValue
        self.sourceId = sourceId
