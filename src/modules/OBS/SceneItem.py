from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Callable

from . import Request, RequestType
from .. import UserStatus


@dataclass
class SceneItem:
    itemId: int
    itemName: str
    enabled: bool
    alert_on_blinking_callback: Callable[..., None] = field(default=None)
    enable_change: datetime = field(default_factory=datetime.now)
    sub_items: Dict[str, Dict[UserStatus, 'SceneItem']] = field(default_factory=dict)
    current_group_name: str = field(default="default")
    has_blinking: bool = field(default=False)
    all_group_names: List[str] = field(default_factory=list)

    @property
    def group_names(self) -> List[str]:
        if not self.all_group_names:
            self.all_group_names =  list(self.sub_items.keys())
        return self.all_group_names

    @property
    def current_subitems(self) -> Dict[UserStatus, 'SceneItem']:
        return self.sub_items[self.current_group_name] if self.current_group_name in self.sub_items.keys() else {}

    def add_sub_item(self, key: UserStatus, sub_item: 'SceneItem', group_name: str = "default") -> None:
        group = self.sub_items.get(group_name, dict())
        sub_item.alert_on_blinking_callback = self.alert_on_blinking
        group[key] = sub_item
        self.sub_items[group_name] = group
        if key == UserStatus.Blinking:
            self.has_blinking = True
            if self.alert_on_blinking_callback is not None: self.alert_on_blinking_callback()

    def alert_on_blinking(self) -> None:
        self.has_blinking = True
        if self.alert_on_blinking_callback is not None: self.alert_on_blinking_callback()

    def change_group(self, name: str) -> None:
        if name in self.group_names:
            self.current_group_name = name

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
