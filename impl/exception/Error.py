class TestExecutionError(Exception):
    """Custom exception for test execution errors """
    pass

class TestScriptError(Exception):
    """Raised when the whole TestScript has to be aborted"""
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

class ValidatorError(TestExecutionError):
    """Raised when the HL7 Validator CLI could not be run at all.

    Subclasses TestExecutionError so a broken validator stops the test and is
    reported as a failure, instead of being mistaken for a clean validation.
    """
    pass

class WarningException(Exception):
    """Exception for non-critical warnings that should not stop test execution"""
    pass

class AssertionFailedContinueError(Exception):
    """Raised when an assertion fails and stopTestOnFail is false or missing — execution continues"""
    pass