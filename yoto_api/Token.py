"""Token.py"""

from dataclasses import dataclass
import datetime as dt


@dataclass
class Token:
    """Token"""

    username: str = None
    password: str = None
    access_token: str = None
    refresh_token: str = None
    id_token: str = None
    scope: str = None
    valid_until: dt.datetime = dt.datetime.min
    token_type: str = None
