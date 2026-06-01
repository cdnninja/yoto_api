"""OAuth token returned by the Auth0 flows."""

from dataclasses import dataclass, field
import datetime as dt


@dataclass
class Token:
    """Access + refresh token. Secret fields are excluded from `repr` so they
    don't leak into logs if a Token is ever printed."""

    access_token: str | None = field(default=None, repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    id_token: str | None = field(default=None, repr=False)
    scope: str | None = None
    valid_until: dt.datetime = dt.datetime.min
    token_type: str | None = None
