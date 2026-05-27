"""Card class"""

from dataclasses import dataclass, field


@dataclass
class Track:
    key: str  # $.card.content.chapters[0].tracks[0].key e.g. "01-INT"
    icon: str | None = (
        None  # $.card.content.chapters[0].tracks[0].display.icon16x16 e.g. "https://card-content.yotoplay.com/yoto/SwcetJ..."
    )
    title: str | None = (
        None  # $.card.content.chapters[0].tracks[0].title e.g. "Introduction"
    )
    duration: int | None = (
        None  # $.card.content.chapters[0].tracks[0].duration e.g. 349
    )
    format: str | None = None  # $.card.content.chapters[0].tracks[0].format e.g. "aac"
    channels: str | None = (
        None  # $.card.content.chapters[0].tracks[0].channels e.g. "mono"
    )
    trackUrl: str | None = (
        None  # $.card.content.chapters[0].tracks[0].trackUrl e.g. "https://secure-media.yotoplay.com/yoto/mYZ6T..."
    )
    type: str | None = None  # $.card.content.chapters[0].tracks[0].type e.g. "audio"


@dataclass
class Chapter:
    key: str  # $.card.content.chapters[0].key e.g. "01-INT"
    icon: str | None = (
        None  # $.card.content.chapters[0].display.icon16x16 e.g. "https://card-content.yotoplay.com/yoto/SwcetJ..."
    )
    title: str | None = None  # $.card.content.chapters[0].title e.g. "Introduction"
    duration: int | None = None  # $.card.content.chapters[0].duration e.g. 349
    tracks: dict[str, Track] = field(
        default_factory=dict
    )  # $.card.content.chapters[0].tracks


@dataclass
class Card:
    id: str  # $.card.cardId e.g. "iYIMF"
    title: str | None = (
        None  # $.card.title e.g. "Ladybird Audio Adventures - Outer Space"
    )
    description: str | None = (
        None  # $.card.metadata.description e.g. "The sky’s the limit for imaginations when it comes to..."
    )
    category: str | None = None  # $.card.metadata.category e.g. "stories"
    author: str | None = None  # $.card.metadata.author e.g. "Ladybird Audio Adventures"
    cover_image_large: str | None = (
        None  # $.card.metadata.cover.imageL e.g. "https://card-content.yotoplay.com/yoto/pub/WgoJMZ..."
    )
    series_title: str | None = (
        None  # $.card.metadata.seriestitle e.g. "Ladybird Audio Adventures Volume 1"
    )
    series_order: int | None = None  # $.card.metadata.seriesorder e.g. 4
    chapters: dict[str, Chapter] = field(
        default_factory=dict
    )  # $.card.content.chapters
