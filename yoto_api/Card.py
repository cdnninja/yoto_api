"""Card class"""

from dataclasses import dataclass


@dataclass
class Track:
    icon: str = None  # $.card.content.chapters[0].tracks[0].display.icon16x16 e.g. "https://card-content.yotoplay.com/yoto/SwcetJ..."
    title: str = None  # $.card.content.chapters[0].tracks[0].title e.g. "Introduction"
    duration: int = None  # $.card.content.chapters[0].tracks[0].duration e.g. 349
    key: str = None  # $.card.content.chapters[0].tracks[0].key e.g. "01-INT"
    format: str = None  # $.card.content.chapters[0].tracks[0].format e.g. "aac"
    channels: str = None  # $.card.content.chapters[0].tracks[0].channels e.g. "mono"
    trackUrl: str = None  # $.card.content.chapters[0].tracks[0].trackUrl e.g. "https://secure-media.yotoplay.com/yoto/mYZ6T..."
    type: str = None  # $.card.content.chapters[0].tracks[0].type e.g. "audio"


@dataclass
class Chapter:
    icon: str = None  # $.card.content.chapters[0].display.icon16x16 e.g. "https://card-content.yotoplay.com/yoto/SwcetJ..."
    title: str = None  # $.card.content.chapters[0].title e.g. "Introduction"
    duration: int = None  # $.card.content.chapters[0].duration e.g. 349
    key: str = None  # $.card.content.chapters[0].key e.g. "01-INT"
    tracks: list[Track] = None  # $.card.content.chapters[0].tracks


@dataclass
class Card:
    id: str = None  # $.card.cardId e.g. "iYIMF"
    title: str = None  # $.card.title e.g. "Ladybird Audio Adventures - Outer Space"
    description: str = None  # $.card.metadata.description e.g. "The sky’s the limit for imaginations when it comes to..."
    category: str = None  # $.card.metadata.category e.g. "stories"
    author: str = None  # $.card.metadata.author e.g. "Ladybird Audio Adventures"
    cover_image_large: str = None  # $.card.metadata.cover.imageL e.g. "https://card-content.yotoplay.com/yoto/pub/WgoJMZ..."
    series_title: str = (
        None  # $.card.metadata.seriestitle e.g. "Ladybird Audio Adventures Volume 1"
    )
    series_order: int = None  # $.card.metadata.seriesorder e.g. 4
    chapters: list[Chapter] = None  # $.card.content.chapters
