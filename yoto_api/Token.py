"""Token.py"""

from dataclasses import dataclass
import datetime as dt


@dataclass
class Token:
    """Token"""

    access_token: str | None = None
    refresh_token: str | None = None
    id_token: str | None = None
    scope: str | None = None
    valid_until: dt.datetime = dt.datetime.min
    token_type: str | None = None
