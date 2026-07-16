from dataclasses import dataclass


@dataclass
class OBSSettings:
    ip: str
    port: int
    password: str
    low_blink_interval: int
    high_blink_interval: int
    blink_time: int
    blink_enabled: bool

    def __ne__(self, other: OBSSettings | None) -> bool:
        if other is None: return True
        return (
            self.ip != other.ip or
            self.port != other.port or
            self.password != other.password or
            self.low_blink_interval != other.low_blink_interval or
            self.high_blink_interval != other.high_blink_interval or
            self.blink_time != other.blink_time or
            self.blink_enabled != other.blink_enabled
        )

    def __str__(self):
        return f"OBS[ip: {self.ip} port: {self.port} password: {self.password} low_blink_interval: {self.low_blink_interval} high_blink_interval: {self.high_blink_interval} blink_time: {self.blink_time} blink_enabled: {self.blink_enabled}]"