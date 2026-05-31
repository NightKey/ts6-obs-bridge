from dataclasses import dataclass
from typing import Dict, Any, Tuple


@dataclass
class Settings:
    teamspeak_ip: str
    teamspeak_port: int
    teamspeak_api: str
    obs_ip: str
    obs_port: int
    obs_password: str
    obs_scene: str

    @staticmethod
    def from_json(json: Dict[str, Any]) -> 'Settings':
        return Settings(
            teamspeak_ip = json["teamspeak_ip"],
            teamspeak_port = json["teamspeak_port"],
            teamspeak_api = json["teamspeak_api"],
            obs_ip = json["obs_ip"],
            obs_port = json["obs_port"],
            obs_password = json["obs_password"],
            obs_scene = json["obs_scene"]
        )

    def to_json(self) -> Dict[str, Any]:
        return {
            "teamspeak_ip" : self.teamspeak_ip,
            "teamspeak_port" : self.teamspeak_port,
            "teamspeak_api" : self.teamspeak_api,
            "obs_ip" : self.obs_ip,
            "obs_port" : self.obs_port,
            "obs_password" : self.obs_password,
            "obs_scene" : self.obs_scene
        }

    def which_changed(self, other: 'Settings') -> Tuple[bool, bool]:
        return (
            self.teamspeak_ip != other.teamspeak_ip or
            self.teamspeak_port != other.teamspeak_port or
            self.teamspeak_api != other.teamspeak_api,
            self.obs_ip != other.obs_ip or
            self.obs_port != other.obs_port or
            self.obs_password != other.obs_password or
            self.obs_scene != other.obs_scene
        )

