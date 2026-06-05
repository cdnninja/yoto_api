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
    """Maps the /card/family/library/groups payload: id, name, familyId,
    imageId, imageUrl, createdAt, lastModifiedAt, items[].contentId."""

    id: str
    name: str | None = None
    family_id: str | None = None
    image_id: str | None = None
    image_url: str | None = None
    created_at: datetime | None = None  # ISO8601 in the payload
    last_modified_at: datetime | None = None  # ISO8601 in the payload
    card_ids: list[str] = field(default_factory=list)
