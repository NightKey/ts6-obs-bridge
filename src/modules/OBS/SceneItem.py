from dataclasses import dataclass, field
from typing import List

from . import Request, RequestType


@dataclass
class SceneItem:
    itemId: int
    itemName: str
    enabled: bool
    sub_items: List['SceneItem'] = field(default_factory=list)

    def get_sub_item(self, item_name: str) -> 'SceneItem | None':
        for item in self.sub_items:
            if item.itemName == item_name:
                return item
        return None

    def add_sub_item(self, sub_item: 'SceneItem') -> None:
        self.sub_items.append(sub_item)

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
