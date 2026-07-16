from dataclasses import dataclass


@dataclass
class TeamSpeakSettings:
    ip: str
    port: int
    api: str

    def __ne__(self, other: TeamSpeakSettings) -> bool:
        return (
            self.ip != other.ip or
            self.port != other.port or
            self.api != other.api
        )

    def __str__(self):
        return f"TeamSpeak[ip: {self.ip} port: {self.port} api: {self.api}]"