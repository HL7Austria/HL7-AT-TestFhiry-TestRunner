class TestExecutionError(Exception):
    """Custom exception for test execution errors """
    pass

class TestScriptError(Exception):
    """Custom exception for stopTestOnFail """
    pass

class OperationError(Exception):
    """Custom exception if operation itself had a problem"""
    pass

class CircularDependencyError(Exception):
    """Raised when fixtures reference each other in a cycle"""
    pass

class UnresolvedReferenceError(Exception):
    """Raised when autocreate fixture has unsolved references after creation"""
    pass

class ReferenceResolutionError(Exception):
    """General reference parsing/resolution errors"""
    pass

class WarningException(Exception):
    """Exception for non-critical warnings that should not stop test execution"""
    pass