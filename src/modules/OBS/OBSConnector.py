import asyncio
from asyncio import timeout, Queue, create_task, Event, Task, Lock, sleep
import base64
import hashlib
from typing import Dict

from smdb_logger import Logger
from websockets import connect, ClientConnection, ConnectionClosedOK, ConnectionClosedError, State, CloseCode
from json import loads, dumps
from time import time
import random

from . import OpCode, SceneItem, Request, RequestType, OBSException
from .. import UserStatus, BaseConnector, async_wrapped, OBSSettings


# Documentation: https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md

class OBSConnector(BaseConnector):
    __logger: Logger
    sync_lock = Lock()
    user_scenes: Dict[str, SceneItem] = {}
    requested_states: Dict[str, UserStatus] = {}
    message_queue: Queue
    blink_enabled: bool
    low_blinking_interval: int
    high_blinking_interval: int
    blink_time: int
    watchdog_loop_task: Task | None = None
    websocket: ClientConnection | None = None
    blinking_tasks: Dict[str, Task] = {}
    obs_initialized_event: Event = Event()
    stop_event: Event = Event()
    stopped: Event = Event()
    failed: bool = False

    @property
    def request_id(self) -> str:
        return f"ts6-obs-bridge-{int(time())}-{random.randint(100,999)}"

    @property
    def is_connected(self) -> bool:
        return self.websocket is not None and self.websocket.state == State.OPEN

    @property
    def logger(self) -> Logger:
        return self.__logger

    @property
    def name(self) -> str:
        return "OBSConnector"

    def __init__(self, logger: Logger):
        self.__logger = logger
        self.stopped.set()

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

    @async_wrapped
    async def watchdog_loop(self):
        self.logger.trace("Starting watchdog loop")
        while not self.stop_event.is_set():
            self.logger.heartbeat(".")
            if not self.obs_initialized_event.is_set() and not self.stopped.is_set():
                await self.__re_init_obs()
            await asyncio.sleep(0.5)
        await self.snapshot_current_state()
        if not self.failed: await self.set_all_user_to(UserStatus.Left)
        await self.__cleanup()

    @async_wrapped
    async def retrieve_loop(self):
        self.logger.debug("Starting retrieve loop")
        while not self.stopped.is_set():
            try:
                async with timeout(0.5):
                    message = await self.websocket.recv()
                    await self.message_queue.put(message)
                self.logger.heartbeat(".")
            except TimeoutError:
                continue
            except ConnectionClosedOK as cco:
                if cco.rcvd.code == CloseCode.NORMAL_CLOSURE: break
                self.logger.warning(f"OBS Closed the connection without error ({cco.rcvd})")
                self.failed = True
                self.stop_event.set()
                self.stopped.set()
            except ConnectionClosedError as cce:
                self.logger.error("OBS Closed connection with error", cce)
                self.failed = True
                self.stop_event.set()
                self.stopped.set()

    @async_wrapped
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

    @async_wrapped
    async def connect(self, settings: OBSSettings) -> bool:
        self.stop_event.clear()
        self.stopped.clear()
        self.message_queue = Queue()
        self.logger.info(f"Connecting to OBS on ws://{settings.ip}:{settings.port}")
        self.websocket = await connect(f"ws://{settings.ip}:{settings.port}/websockets")
        create_task(self.retrieve_loop(), name="OBS retrieve task")
        # Adapted from Elektordi(https://github.com/Elektordi/obs-websocket-py/blob/master/obswebsocket/core.py) , MIT License
        response = await self.get_message(OpCode.Hello)
        auth = ""
        if 'authentication' in response['d']:
            secret = base64.b64encode(
                hashlib.sha256(
                    (settings.password + response['d']['authentication']['salt']).encode('utf-8')
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

        self.logger.debug(f"OBS Connected. Requested states: {[user + '-' + state.name for user, state in self.requested_states.items()]}")
        self.blink_enabled = settings.blink_enabled
        self.low_blinking_interval = settings.low_blink_interval
        self.high_blinking_interval = settings.high_blink_interval
        self.blink_time = settings.blink_time
        await self.init_obs()
        self.failed = False
        self.watchdog_loop_task = create_task(self.watchdog_loop(), name="OBS watchdog task")
        return True

    def close(self) -> None:
        if self.stop_event.is_set(): return
        self.logger.info("Closing OBS connector")
        self.stop_event.set()
        if self.watchdog_loop_task is None:
            self.stopped.set()

    @async_wrapped
    async def __cleanup(self) -> None:
        self.logger.info("Cleanup")
        await self.websocket.close()
        self.websocket = None
        self.user_scenes.clear()
        self.watchdog_loop_task = None
        self.stopped.set()

    @async_wrapped
    async def snapshot_current_state(self) -> None:
        self.logger.debug("Snapshotting current state")
        for user, data in self.user_scenes.items():
            state = UserStatus.Left
            for key, item in data.sub_items.items():
                if item.enabled:
                    state = key
                    break
            if state == UserStatus.Left: continue
            self.logger.debug(f"{user}: {state}")
            self.requested_states[user] = state

    @async_wrapped
    async def re_init_obs(self) -> None:
        self.obs_initialized_event.clear()
        while not self.obs_initialized_event.is_set():
            await asyncio.sleep(0.1)

    @async_wrapped
    async def __re_init_obs(self) -> None:
        self.user_scenes.clear()
        await self.init_obs()

    @async_wrapped
    async def init_obs(self) -> None:
        self.logger.info("Initializing OBS")
        data = Request(RequestType.GetSceneList, self.request_id).to_request_dict()
        self.logger.debug("Getting all available scenes")
        await self.send(data, OpCode.Request)
        response = await self.get_message(required_op_code=OpCode.RequestResponse)
        self.logger.trace(f"Scene bulk request response: {response}")
        if not response['d']["requestStatus"]["result"]:
            self.logger.warning("Failed to get scene list.")
            await self.__cleanup()
            raise OBSException("Failed to get scene list.")
        for scene in response['d']["responseData"]['scenes']:
            name = scene["sceneName"]
            if "ts6-obs-" in name:
                scene_user = name.split('ts6-obs-')[-1]
                item = SceneItem(itemName=name, itemId=scene["sceneIndex"], enabled=scene_user in self.requested_states)
                self.user_scenes[scene_user] = item
                await self.set_all_to_known(item, scene_user)
                if item.enabled:
                    del self.requested_states[scene_user]
                    self.add_blinking_to_user(scene_user, item)
        self.obs_initialized_event.set()

    def add_blinking_to_user(self, scene_user: str, scene: SceneItem):
        if UserStatus.Blinking in scene.sub_items.keys() and self.blink_enabled:
            self.blinking_tasks[scene_user] = create_task(self.blinking_task(scene_user), name=f"{scene_user} blinking task")

    @async_wrapped
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
            subitem_name = item["sourceName"].split('-')[-1]
            sub_item = SceneItem(
                itemName=subitem_name,
                itemId=item["sceneItemId"],
                enabled=scene_user in self.requested_states and subitem_name == self.requested_states[scene_user].value
            )
            self.logger.trace(f"Scene request created for {scene.itemName}-{subitem_name}. IsEnabled: {sub_item.enabled}")
            requests.append(sub_item.get_request(scene.itemName, self.request_id).to_request_dict())
            scene.add_sub_item(UserStatus(subitem_name), sub_item)

        if len(request) == 0: return
        batch_request = {
            "requestId": self.request_id,
            "executionType": 2,
            "requests": requests
        }
        await self.send(batch_request, OpCode.RequestBatch)
        await self.get_message(OpCode.RequestBatchResponse)

    @async_wrapped
    async def set_all_user_to(self, target_state: UserStatus, only_present: bool = False) -> None:
        for name in self.user_scenes.keys():
            await self.set_user_to(name, target_state, only_present)

    @async_wrapped
    async def blinking_task(self, user: str) -> None:
        if self.blink_time is None or self.low_blinking_interval is None or self.high_blinking_interval is None:
            self.logger.trace(f"Tried to create blinking task for {user} when some blinking values are None")
            return
        if self.user_scenes.get(user, None) is None or UserStatus.Blinking not in self.user_scenes.get(user).sub_items.keys(): return
        self.logger.debug(f"Creating blinking task for {user}")
        while not self.stop_event.is_set():
            await sleep(random.randint(self.low_blinking_interval, self.high_blinking_interval) / 1000)
            user_scene = self.user_scenes.get(user, None)
            if user_scene is None or not user_scene.enabled: continue
            await self.try_blinking(user, UserStatus.Blinking)
            await sleep(self.blink_time / 1000)
            await self.try_blinking(user, UserStatus.Quiet)

    @async_wrapped
    async def try_blinking(self, user: str, target_status: UserStatus) -> None:
        user_scene = self.user_scenes.get(user)
        quiet = user_scene.sub_items[UserStatus.Quiet]
        blinking = user_scene.sub_items[UserStatus.Blinking]
        if not quiet.enabled and not blinking.enabled: return
        await self.set_user_to(user, target_status)

    @async_wrapped
    async def set_user_to(self, name: str, target_state: UserStatus, only_present: bool = False) -> None:
        if not self.is_connected:
            if target_state == UserStatus.Left.value:
                if name in self.requested_states.keys():
                    del self.requested_states[name]
                return
            self.requested_states[name] = target_state
            return
        requests = []
        self.logger.debug(f"Setting {name} user's scene to {target_state.name}")
        scene = self.user_scenes.get(name, None)
        if scene is None or (not scene.enabled and only_present): return
        if target_state != UserStatus.Left.value:
            self.add_blinking_to_user(name, scene)
        scene.enabled = target_state.value != UserStatus.Left.value
        for key, item in scene.sub_items.items():
            new_state = item.itemName == target_state.value
            if item.enabled and new_state: return # Same state True, already set to that.
            if not item.enabled and not new_state: continue # Same false, no need to send all 3 request, when someone leaves.
            item.enabled = new_state
            requests.append(item.get_request(scene.itemName, self.request_id).to_request_dict())

        batch_request = {
            "requestId": self.request_id,
            "executionType": 2,
            "requests": requests
        }
        await self.send(batch_request, OpCode.RequestBatch)
        await self.get_message(OpCode.RequestBatchResponse)

    @async_wrapped
    async def toggle_deafen(self, is_deafened: bool):
        self.logger.debug(f"Toggling deafen to {is_deafened}")
        await self.set_all_user_to(UserStatus.Muted if is_deafened else UserStatus.Quiet, only_present=True)


    def get_scene_map(self) -> dict:
        return {"connected": self.is_connected, "message_queue":self.message_queue.qsize(), "scenes":[{"name": name, "present": scene.enabled, "all": [{"name":x.itemName, "enabled":x.enabled} for k, x in scene.sub_items.items()]} for name, scene in self.user_scenes.items()]}
