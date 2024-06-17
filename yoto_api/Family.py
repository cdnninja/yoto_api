from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict


@dataclass
class Device:
    deviceId: str
    addedAt: datetime


@dataclass
class Member:
    createdAt: datetime
    email: str
    emailVerified: bool
    lastIp: str
    lastLoginAt: datetime
    loginsCount: int
    picture: str
    userId: str
    addedAt: datetime


@dataclass
class Family:
    familyId: str
    createdAt: datetime
    devices: List[Device]
    members: List[Member]
    country: str

    def __init__(self, data: Dict) -> None:
        self.familyId = data["familyId"]
        self.createdAt = datetime.fromisoformat(data["createdAt"].rstrip("Z"))

        self.devices = [
            Device(
                deviceId=device["deviceId"],
                addedAt=datetime.fromisoformat(device["addedAt"].rstrip("Z")),
            )
            for device in data["devices"]
        ]

        self.members = [
            Member(
                createdAt=datetime.fromisoformat(member["createdAt"].rstrip("Z")),
                email=member["email"],
                emailVerified=member["emailVerified"],
                lastIp=member["lastIp"],
                lastLoginAt=datetime.fromisoformat(member["lastLoginAt"].rstrip("Z")),
                loginsCount=member["loginsCount"],
                picture=member["picture"],
                userId=member["userId"],
                addedAt=datetime.fromisoformat(member["addedAt"].rstrip("Z")),
            )
            for member in data["members"]
        ]

        self.country = data["country"]
