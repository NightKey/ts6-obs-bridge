from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class ClientInfo:
    id: int
    name: str
    channel_id: int | None
    is_talking: bool | None
    is_muted: bool | None
    is_deafened: bool | None
    is_muted_by_user: bool | None

    @classmethod
    def from_dict(cls, data: Dict[str, Any], id: int | None = None) -> 'ClientInfo':
        return ClientInfo(
            id=id if id is not None else data["id"],
            name=data["properties"]["nickname"] if "nickname" in data["properties"] else "Unknown User",
            is_talking=data["properties"]["isTalker"] if "isTalker" in data["properties"] else None,
            is_muted=data["properties"]["inputMuted"] if "inputMuted" in data["properties"] else None,
            is_deafened=data["properties"]["outputMuted"] if "outputMuted" in data["properties"] else None,
            is_muted_by_user=data["properties"]["isMuted"] if "isMuted" in data["properties"] else None,
            channel_id=data["channelId"] if "channelId" in data else None
        )

    def merge(self, other: 'ClientInfo') -> 'ClientInfo':
        return ClientInfo(
            id=self.id,
            name=other.name if other.name else self.name,
            is_talking=other.is_talking if other.is_talking is not None else self.is_talking,
            is_muted=other.is_muted if other.is_muted is not None else self.is_muted,
            is_deafened =other.is_deafened if other.is_deafened is not None else self.is_deafened,
            is_muted_by_user =other.is_muted_by_user if other.is_muted_by_user is not None else self.is_muted_by_user,
            channel_id=other.channel_id if other.channel_id is not None else self.channel_id
        )

    def with_new_channel(self, channel_id: int) -> 'ClientInfo':
        return ClientInfo(
            id=self.id,
            name=self.name,
            channel_id=channel_id,
            is_talking=self.is_talking,
            is_muted=self.is_muted,
            is_deafened=self.is_deafened,
            is_muted_by_user=self.is_muted_by_user
        )