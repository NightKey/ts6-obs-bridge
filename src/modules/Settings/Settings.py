from dataclasses import dataclass
from typing import Dict, Any, Tuple

from . import OBSSettings, TeamSpeakSettings


@dataclass
class Settings:
    teamspeak: TeamSpeakSettings
    obs: OBSSettings
    autoconnect: bool
    host: str
    port: int

    @staticmethod
    def from_json(json: Dict[str, Any]) -> 'Settings':
        teamspeak_settings = TeamSpeakSettings(
            ip=json["teamspeak_ip"],
            port = json["teamspeak_port"],
            api = json["teamspeak_api"]
        )
        obs_settings = OBSSettings(
            ip=json["obs_ip"],
            port=json["obs_port"],
            password=json["obs_password"],
            low_blink_interval=json.get("low_blink_interval", None),
            high_blink_interval=json.get("high_blink_interval", None),
            blink_time=json.get("blink_time", None),
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
            "teamspeak_ip" : self.teamspeak.ip,
            "teamspeak_port" : self.teamspeak.port,
            "teamspeak_api" : self.teamspeak.api,
            "obs_ip" : self.obs.ip,
            "obs_port" : self.obs.port,
            "obs_password" : self.obs.password,
            "low_blink_interval": self.obs.low_blink_interval,
            "high_blink_interval": self.obs.high_blink_interval,
            "blink_time": self.obs.blink_time,
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
