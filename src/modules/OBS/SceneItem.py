from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

from . import Request, RequestType
from .. import UserStatus


@dataclass
class SceneItem:
    itemId: int
    itemName: str
    enabled: bool
    enable_change: datetime = field(default_factory=datetime.now)
    sub_items: Dict[UserStatus, 'SceneItem'] = field(default_factory=dict)

    def add_sub_item(self, key: UserStatus, sub_item: 'SceneItem') -> None:
        self.sub_items[key] = sub_item

    def get_request(self, parent_name: str, request_id: str) -> Request:
        return Request(
            RequestType.SetSceneItemEnabled,
            request_id,
            requestData={
                "sceneName": parent_name,
                "sceneItemId": self.itemId,
                "sceneItemEnabled": self.enabled
            }
        )
