"""exceptions.py"""


class YotoException(Exception):
    """
    Generic YotoException exception.
    """

    pass


class AuthenticationError(YotoException):
    """
    Raised upon receipt of an authentication error.
    """

    pass
