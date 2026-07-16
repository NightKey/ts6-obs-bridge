from dataclasses import dataclass


@dataclass
class OBSSettings:
    ip: str
    port: int
    password: str
    low_blink_interval: int | None
    high_blink_interval: int | None
    blink_time: int | None

    def __ne__(self, other: OBSSettings) -> bool:
        return (
            self.ip != other.ip or
            self.port != other.port or
            self.password != other.password or
            self.low_blink_interval != other.low_blink_interval or
            self.high_blink_interval != other.high_blink_interval or
            self.blink_time != other.blink_time
        )

    def __str__(self):
        return f"OBS[ip: {self.ip} port: {self.port} password: {self.password} low_blink_interval: {self.low_blink_interval} high_blink_interval: {self.high_blink_interval} blink_time: {self.blink_time}]"