from dataclasses import dataclass

from typing import Optional


@dataclass
class TeamSpeakSettings:
    ip: str
    port: int
    api: str

    def __ne__(self, other: Optional['TeamSpeakSettings']) -> bool:
        if other is None: return True
        return (
            self.ip != other.ip or
            self.port != other.port or
            self.api != other.api
        )

    def __str__(self):
        return f"TeamSpeak[ip: {self.ip} port: {self.port} api: {self.api}]"