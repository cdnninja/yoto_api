"""exceptions.py"""


class YotoError(Exception):
    pass


class AuthenticationError(YotoError):
    """
    Raised upon receipt of an authentication error.
    """


class YotoAPIError(YotoError):
    """Raised on REST transport, HTTP, or JSON-decoding failures.

    `status_code` carries the HTTP status when the failure is a non-2xx
    response, so callers don't have to string-match on the message to
    detect specific status codes (e.g. 403 for missing scope).
    """

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class YotoMQTTError(YotoError):
    pass
