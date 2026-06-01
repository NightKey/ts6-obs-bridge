from asyncio import timeout, Queue, create_task, Event
import base64
import hashlib
from typing import Callable, Tuple, Dict

from smdb_logger import Logger
from websockets import connect, ClientConnection, ConnectionClosedOK, ConnectionClosedError
from json import loads, dumps
from time import time
import random

from . import OpCode, SceneItem, Request, RequestType, OBSException
from .. import Status, UserStatus

# Documentation: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md

class OBSConnector:
    logger: Logger
    scene: str
    user_scenes: Dict[str, Tuple[SceneItem, bool]] = {}
    stopping: Event = Event()
    message_queue: Queue = Queue()
    websocket: ClientConnection | None = None
    connection_failed_callback: Callable[[Status], None]

    @property
    def request_id(self) -> str:
        return f"ts6-obs-bridge-{int(time())}-{random.randint(100,999)}"

    @property
    def is_connected(self) -> bool:
        return self.websocket is not None

    def __init__(self, logger: Logger, connection_failed_callback: Callable[[Status], None]):
        self.logger = logger
        self.connection_failed_callback = connection_failed_callback

    async def send(self, data: dict, op_code: OpCode):
        self.logger.trace(f"Sending opcode: {op_code.name}")
        await self.websocket.send(
            dumps(
                {
                    "op": op_code.value,
                    "d": data
                }
            )
        )

    async def retrieve_loop(self):
        self.logger.debug("Starting retrieve loop")
        while not self.stopping.is_set():
            try:
                async with timeout(0.5):
                    message = await self.websocket.recv()
                    await self.message_queue.put(message)
            except TimeoutError:
                continue
            except ConnectionClosedOK:
                self.logger.warning("OBS Closed the connection without error")
                self.connection_failed_callback(Status.OBSNotReady)
                await self.close()
            except ConnectionClosedError as cce:
                self.logger.error("OBS Closed connection with error", cce)
                self.connection_failed_callback(Status.OBSNotReady)
                await self.close()

    async def get_message(self, required_op_code: OpCode) -> dict:
        message = await self.message_queue.get()
        if not message:
            await self.websocket.close()
            self.websocket = None
            raise OBSException("Empty response retrieved, incorrect password")
        response = loads(message)
        if response['op'] != required_op_code.value:
            await self.websocket.close()
            self.websocket = None
            raise OBSException(f"Response identifier {response['op']} is not valid {required_op_code.value}")
        return response

    async def connect(self, obs_ip: str, obs_port: int, obs_password: str, obs_scene: str) -> Status:
        self.stopping.clear()
        self.logger.info(f"Connecting to OBS on ws://{obs_ip}:{obs_port} with scene: {obs_scene}")
        self.scene = obs_scene
        self.websocket = await connect(f"ws://{obs_ip}:{obs_port}/websockets")
        create_task(self.retrieve_loop())
        # Adapted from Elektordi(https://github.com/Elektordi/obs-websocket-py/blob/master/obswebsocket/core.py) , MIT License
        response = await self.get_message(OpCode.Hello)
        auth = ""
        if 'authentication' in response['d']:
            secret = base64.b64encode(
                hashlib.sha256(
                    (obs_password + response['d']['authentication']['salt']).encode('utf-8')
                ).digest()
            )
            auth = base64.b64encode(
                hashlib.sha256(
                    secret + response['d']['authentication']['challenge'].encode('utf-8')
                ).digest()
            ).decode('utf-8')
        else:
            self.logger.warning("Password authentication is recommended, but not present!")

        self.logger.debug("Sending identify request")
        await self.send(
            {
                "rpcVersion": 1,
                "authentication": auth,
                "eventSubscriptions": 0
            },
            OpCode.Identify
        )

        response = await self.get_message(OpCode.Identified)
        self.logger.trace(f"Identify response: {response}")
        if response['d'].get('negotiatedRpcVersion') != 1:
            await self.websocket.close()
            self.websocket = None
            raise OBSException("Bad RpcVersion")

        await self.init_obs()
        return Status.OBSReady

    async def close(self):
        if self.websocket is None: return
        self.logger.info("Closing OBS connector")
        self.stopping.set()
        await self.websocket.close()
        self.websocket = None

    async def init_obs(self) -> None:
        self.logger.info("Initializing OBS")
        data = Request(RequestType.GetSceneList, self.request_id).to_request_dict()
        self.logger.debug("Getting all available scenes")
        await self.send(data, OpCode.Request)
        response = await self.get_message(required_op_code=OpCode.RequestResponse)
        self.logger.trace(f"Scene bulk request response: {response}")
        if not response['d']["requestStatus"]["result"]:
            self.logger.warning("Failed to get scene list.")
            raise OBSException("Failed to get scene list.")
        for scene in response['d']["responseData"]['scenes']:
            name = scene["sceneName"]
            if "ts6-obs-" in name:
                item = SceneItem(itemName=name, itemId=scene["sceneIndex"])
                self.user_scenes[name.split('ts6-obs-')[-1]] = (item, False)
                await self.set_all_to_known_off(item)

    async def set_all_to_known_off(self, scene: SceneItem) -> None:
        self.logger.debug(f"Setting {scene} to a known, all off state")
        request = Request(
            requestType=RequestType.GetSceneItemList,
            requestId=self.request_id,
            requestData={"sceneName": scene.itemName}
        ).to_request_dict()
        await self.send(request, OpCode.Request)
        response = await self.get_message(required_op_code=OpCode.RequestResponse)
        if not response['d']["requestStatus"]["result"]:
            self.logger.error(f"Failed to get item list for scene {scene.itemName}.")
            return
        requests = []
        for item in response['d']["responseData"]["sceneItems"]:
            requests.append(
                Request(
                    RequestType.SetSceneItemEnabled,
                    self.request_id,
                    requestData={
                        "sceneName": scene.itemName,
                        "sceneItemId": item["sceneItemId"],
                        "sceneItemEnabled": False
                    }
                ).to_request_dict()
            )
            scene.add_sub_item(SceneItem(itemName=item["sourceName"], itemId=item["sceneItemId"]))
        batch_request = {
            "requestId": self.request_id,
            "executionType": 2,
            "requests": requests
        }
        await self.send(batch_request, OpCode.RequestBatch)
        await self.get_message(OpCode.RequestBatchResponse)

    async def set_scene_to(self, scene: SceneItem, target_state: UserStatus) -> None:
        requests = []
        self.logger.debug(f"Setting all sub-items in {scene} to {target_state}.")
        for item in scene.sub_items:
            item.enabled = item.itemName == target_state.value
            requests.append(
                Request(
                    RequestType.SetSceneItemEnabled,
                    self.request_id,
                    requestData={
                        "sceneName": scene.itemName,
                        "sceneItemId": item.itemId,
                        "sceneItemEnabled": item.itemName == target_state.value
                    }
                ).to_request_dict()
            )

        batch_request = {
            "requestId": self.request_id,
            "executionType": 2,
            "requests": requests
        }
        await self.send(batch_request, OpCode.RequestBatch)
        await self.get_message(OpCode.RequestBatchResponse)

    async def change_state(self, user: str, from_state: UserStatus | None, target_state: UserStatus) -> None:
        self.logger.info(f"Changing {user} state from {from_state} to {target_state}")
        if user not in self.user_scenes:
            return
        (scene, present) = self.user_scenes[user]
        self.user_scenes[user] = (scene, target_state.name != UserStatus.Left.name)
        requests = []
        if from_state is not None and from_state.name != UserStatus.Left.name:
            from_state_item_id = [x for x in scene.sub_items if x.itemName == from_state.value][0].itemId
            requests.append(
                Request(
                    requestType=RequestType.SetSceneItemEnabled,
                    requestId=self.request_id,
                    requestData={
                        "sceneName": scene.itemName,
                        "sceneItemId": from_state_item_id,
                        "sceneItemEnabled": False
                    }
                ).to_request_dict()
            )
        if target_state.name != UserStatus.Left.name:
            target_state_item_id = [x for x in scene.sub_items if x.itemName == target_state.value][0].itemId
            requests.append(
                Request(
                    requestType=RequestType.SetSceneItemEnabled,
                    requestId=self.request_id,
                    requestData={
                        "sceneName": scene.itemName,
                        "sceneItemId": target_state_item_id,
                        "sceneItemEnabled": True
                    }
                ).to_request_dict()
            )
        if not requests: return
        batch_request = {
            "requestId": self.request_id,
            "executionType": 2,
            "requests": requests
        }
        await self.send(batch_request, OpCode.RequestBatch)
        response = await self.get_message(OpCode.RequestBatchResponse)
        self.logger.debug(f"{response}")

    async def toggle_deafen(self, is_deafened: bool):
        self.logger.debug(f"Toggling deafen to {is_deafened}")
        for _, (scene, present) in self.user_scenes.items():
            if present:
                await self.set_scene_to(scene, UserStatus.Muted if is_deafened else UserStatus.Quiet)

    def get_scene_map(self) -> dict:
        return {"message_queue":self.message_queue.qsize(), "scenes":[{"name": name, "present": present, "all": [x.itemName for x in scene.sub_items]} for name, (scene, present) in self.user_scenes.items()]}
