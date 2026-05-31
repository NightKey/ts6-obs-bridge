from dataclasses import dataclass, field

from modules.OBS import RequestType


@dataclass
class Request:
    requestType: RequestType
    requestId: str
    requestData: dict | None = field(default=None)

    def to_request_dict(self) -> dict:
        data: dict[str, str | dict] = {
            "requestType": self.requestType.value,
            "requestId": self.requestId
        }
        if self.requestData is not None:
            data["requestData"] = self.requestData
        return data