from dataclasses import dataclass
from enum import Enum

from typing import Optional

@dataclass
class TeamSpeakSettings:
    ip: str
    port: int
    api: str
    user_mute_behavior: bool

    def __ne__(self, other: Optional['TeamSpeakSettings']) -> bool:
        if other is None: return True
        return (
                self.ip != other.ip or
                self.port != other.port or
                self.api != other.api or
                self.user_mute_behavior != other.user_mute_behavior
        )

    def copy(self) -> 'TeamSpeakSettings':
        return TeamSpeakSettings(
            ip=self.ip,
            port=self.port,
            api=self.api,
            user_mute_behavior=self.user_mute_behavior
        )

    def __str__(self):
        return f"TeamSpeak[ip: {self.ip} port: {self.port} api: {self.api} user_mute_behavior: {'Left' if self.user_mute_behavior else 'Muted'}]"