from enum import Enum


class RequestType(Enum):
    GetSceneList = "GetSceneList"
    SetSceneItemEnabled = "SetSceneItemEnabled"
    GetSceneItemList = "GetSceneItemList"