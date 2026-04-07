class TestExecutionError(Exception):
    """Custom exception for test execution errors """
    pass

class TestScriptError(Exception):
    """Custom exception for stopTestOnFail """
    pass

class OperationError(Exception):
    """Custom exception if operation itself had a problem"""
    pass