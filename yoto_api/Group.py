"""Group class — a Yoto family library group.

Groups are user-defined labels over library cards: a card can belong to
several groups at once, and adding it to a group doesn't remove it from
the main library. A Group holds the card IDs only; the card metadata
itself lives in `YotoClient.library` (refresh it with `update_library`).
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Group:
    id: str  # $.[0].id e.g. "wXyZ1"
    name: str | None = None  # $.[0].name e.g. "Bedtime"
    family_id: str | None = None  # $.[0].familyId
    image_id: str | None = None  # $.[0].imageId
    image_url: str | None = (
        None  # $.[0].imageUrl e.g. "https://card-content.yotoplay.com/yoto/..."
    )
    created_at: datetime | None = None  # $.[0].createdAt (ISO8601)
    last_modified_at: datetime | None = None  # $.[0].lastModifiedAt (ISO8601)
    card_ids: list[str] = field(
        default_factory=list
    )  # $.[0].items[].contentId (card IDs in this group)
