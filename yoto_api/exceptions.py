"""exceptions.py"""


class YotoError(Exception):
    pass


class AuthenticationError(YotoError):
    """
    Raised upon receipt of an authentication error.
    """

    pass


class YotoAPIError(YotoError):
    pass


class YotoMQTTError(YotoError):
    pass
