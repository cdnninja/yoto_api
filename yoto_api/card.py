"""Card class"""

from dataclasses import dataclass

@dataclass
class Card:
    id: str = None
    title: str = None
