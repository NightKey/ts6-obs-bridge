from dataclasses import dataclass, field
from typing import Dict, Any, Tuple

from . import OBSSettings, TeamSpeakSettings


@dataclass
class Settings:
    teamspeak: TeamSpeakSettings | None = field(default=None)
    obs: OBSSettings | None = field(default=None)
    autoconnect: bool = field(default=False)
    host: str = field(default="127.0.0.1")
    port: int = field(default=12345)

    @staticmethod
    def from_json(json: Dict[str, Any]) -> 'Settings':
        teamspeak_settings = TeamSpeakSettings(
            ip = json["teamspeak_ip"],
            port = json["teamspeak_port"],
            api = json["teamspeak_api"]
        )
        obs_settings = OBSSettings(
            ip=json["obs_ip"],
            port=json["obs_port"],
            password=json["obs_password"],
            low_blink_interval=json.get("low_blink_interval", 1000),
            high_blink_interval=json.get("high_blink_interval", 3000),
            blink_time=json.get("blink_time", 150),
            blink_enabled=json.get("blink_enabled", False),
        )
        return Settings(
            teamspeak=teamspeak_settings,
            obs=obs_settings,
            autoconnect= bool(json.get("autoconnect", 0)),
            host=json.get("host", "127.0.0.1"),
            port=json.get("port", 12345)
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "teamspeak_ip" : self.teamspeak.ip if self.teamspeak is not None else None,
            "teamspeak_port" : self.teamspeak.port if self.teamspeak is not None else None,
            "teamspeak_api" : self.teamspeak.api if self.teamspeak is not None else None,
            "obs_ip" : self.obs.ip if self.obs is not None else None,
            "obs_port" : self.obs.port if self.obs is not None else None,
            "obs_password" : self.obs.password if self.obs is not None else None,
            "low_blink_interval": self.obs.low_blink_interval if self.obs is not None else None,
            "high_blink_interval": self.obs.high_blink_interval if self.obs is not None else None,
            "blink_time": self.obs.blink_time if self.obs is not None else None,
            "blink_enabled": self.obs.blink_enabled if self.obs is not None else False,
            "autoconnect" : self.autoconnect,
            "host": self.host,
            "port": self.port,
        }

    def which_changed(self, other: 'Settings') -> Tuple[bool, bool]:
        return (
            self.teamspeak != other.teamspeak,
            self.obs != other.obs
        )

    def __str__(self) -> str:
        return f"Settings[{self.teamspeak} {self.obs} autoconnect: {self.autoconnect} host: {self.host} port: {self.port}]"
