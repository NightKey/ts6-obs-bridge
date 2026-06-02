from asyncio import timeout, Queue, create_task, Event
import base64
import hashlib
from typing import Callable, Tuple, Dict

from smdb_logger import Logger
from websockets import connect, ClientConnection, ConnectionClosedOK, ConnectionClosedError, State
from json import loads, dumps
from time import time
import random

from . import OpCode, SceneItem, Request, RequestType, OBSException
from .. import Status, UserStatus

# Documentation: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md

class OBSConnector:
    logger: Logger
    scene: str
    user_scenes: Dict[str, SceneItem] = {}
    requested_states: Dict[str, UserStatus] = {}
    stopping: Event = Event()
    message_queue: Queue = Queue()
    websocket: ClientConnection | None = None
    connection_failed_callback: Callable[[Status], None]

    @property
    def request_id(self) -> str:
        return f"ts6-obs-bridge-{int(time())}-{random.randint(100,999)}"

    @property
    def is_connected(self) -> bool:
        return self.websocket is not None and self.websocket.state == State.OPEN

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
                scene_user = name.split('ts6-obs-')[-1]
                item = SceneItem(itemName=name, itemId=scene["sceneIndex"], enabled=scene_user in self.requested_states)
                self.user_scenes[scene_user] = item
                await self.set_all_to_known(item, scene_user)
                if scene_user in self.requested_states: del self.requested_states[scene_user]

    async def set_all_to_known(self, scene: SceneItem, scene_user: str) -> None:
        self.logger.debug(f"Setting {scene} to a known, all off state if no request was for that name")
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
            subitem_name = item["sourceName"]
            sub_item = SceneItem(itemName=subitem_name, itemId=item["sceneItemId"], enabled=scene_user in self.requested_states and subitem_name == self.requested_states[scene_user].value)
            requests.append(sub_item.get_request(scene.itemName,self.request_id).to_request_dict())
            scene.add_sub_item(sub_item)

        if len(request) == 0: return
        batch_request = {
            "requestId": self.request_id,
            "executionType": 2,
            "requests": requests
        }
        await self.send(batch_request, OpCode.RequestBatch)
        await self.get_message(OpCode.RequestBatchResponse)

    async def set_user_to(self, name: str, target_state: UserStatus, only_present: bool = False) -> None:
        if not self.is_connected:
            self.requested_states[name] = target_state
            return
        requests = []
        self.logger.debug(f"Setting {name} user's scene to {target_state.name}")
        scene = self.user_scenes.get(name, None)
        if scene is None or (not scene.enabled and only_present): return
        scene.enabled = target_state.value != UserStatus.Left.value
        for item in scene.sub_items:
            new_state = item.itemName == target_state.value
            if item.enabled and new_state: return # Same state True, already set to that.
            if not item.enabled and not new_state: continue # Same false, no need to send all 3 request, when someone leaves.
            item.enabled =  new_state
            requests.append(item.get_request(scene.itemName, self.request_id).to_request_dict())

        batch_request = {
            "requestId": self.request_id,
            "executionType": 2,
            "requests": requests
        }
        await self.send(batch_request, OpCode.RequestBatch)
        await self.get_message(OpCode.RequestBatchResponse)

    async def toggle_deafen(self, is_deafened: bool):
        self.logger.debug(f"Toggling deafen to {is_deafened}")
        for name in self.user_scenes.keys():
            await self.set_user_to(name, UserStatus.Muted if is_deafened else UserStatus.Quiet, only_present=True)

    def get_scene_map(self) -> dict:
        return {"message_queue":self.message_queue.qsize(), "scenes":[{"name": name, "present": scene.enabled, "all": [{"name":x.itemName, "enabled":x.enabled} for x in scene.sub_items]} for name, scene in self.user_scenes.items()]}
