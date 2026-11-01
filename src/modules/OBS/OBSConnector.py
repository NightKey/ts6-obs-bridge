import asyncio
from asyncio import timeout, Queue, create_task, Event, Task, Lock, sleep
import base64
import hashlib
from typing import Dict, List

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
    current_state: Dict[str, UserStatus] = {}
    current_groups: Dict[str, str] = {}
    current_group: str = "default"
    select_group: str = "default"
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
        self.logger.debug(f"Sending opcode: {op_code.name}")
        self.logger.trace(f"Data: {data}")
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
            if self.select_group != self.current_group:
                if not await self.set_group(self.select_group):
                    self.select_group = self.current_group
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
        self.logger.debug(f"Watchdog exiting because {'stopped is set' if self.stopped.is_set() else 'no idea'}")

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
        for task in self.blinking_tasks.values():
            task.cancel()
        self.websocket = None
        self.user_scenes.clear()
        self.watchdog_loop_task = None
        self.stopped.set()

    @async_wrapped
    async def snapshot_current_state(self) -> None:
        self.logger.debug("Snapshotting current state")
        for user, data in self.user_scenes.items():
            state = UserStatus.Left
            for key, item in data.current_subitems.items():
                if item.enabled:
                    state = key
                    break
            if state == UserStatus.Left: continue
            group = data.current_group_name
            self.logger.debug(f"{user}: [{group}] {state}")
            self.requested_states[user] = state
            self.current_groups[user] = group

    @async_wrapped
    async def re_init_obs(self) -> None:
        self.obs_initialized_event.clear()
        while not self.obs_initialized_event.is_set():
            await asyncio.sleep(0.1)

    @async_wrapped
    async def __re_init_obs(self) -> None:
        self.user_scenes.clear()
        self.current_groups.clear()
        self.select_group = "default"
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
                await self.fill_and_set_sub_items(item, scene_user)
                if item.enabled:
                    del self.requested_states[scene_user]
                    self.add_blinking_to_user(scene_user, item)
        self.obs_initialized_event.set()

    def add_blinking_to_user(self, scene_user: str, scene: SceneItem):
        if scene.has_blinking and self.blink_enabled:
            self.logger.debug(f"Adding blinking to user {scene_user}")
            self.blinking_tasks[scene_user] = create_task(self.blinking_task(scene_user), name=f"{scene_user} blinking task")

    @async_wrapped
    async def fill_and_set_sub_items(self, scene: SceneItem, scene_user: str) -> None:
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
        temp_statuses: Dict[str, Dict[UserStatus, SceneItem]] = {}
        for item in response['d']["responseData"]["sceneItems"]:
            subitem_name = item["sourceName"].split('-')[-1]
            if '-:' in item["sourceName"] and ':-' in item["sourceName"]:
                group_name = item["sourceName"].split('-:')[-1].split(':-')[0]
            else:
                group_name = "default"
            sub_item = SceneItem(
                itemName=subitem_name,
                itemId=item["sceneItemId"],
                enabled=scene_user in self.requested_states and subitem_name == self.requested_states[scene_user].value and group_name == self.current_group
            )
            self.logger.trace(f"Scene request created for {scene.itemName}-{subitem_name}. IsEnabled: {sub_item.enabled}")
            requests.append(sub_item.get_request(scene.itemName, self.request_id).to_request_dict())
            try:
                status = UserStatus.from_string(subitem_name)
            except NotImplementedError:
                continue
            if status == UserStatus.Blinking:
                parent_string = item["sourceName"].split('-')[-2]
                try:
                    parent_status = UserStatus.from_string(parent_string)
                    if group_name not in temp_statuses:
                        temp_statuses[group_name] = {}
                    if parent_status not in scene.sub_items.keys():
                        temp_statuses[group_name][parent_status] = sub_item
                    else:
                        scene.sub_items[group_name][parent_status].add_sub_item(status, sub_item)
                        self.logger.debug(f"Scene subitem added to \"{scene.sub_items[group_name][parent_status].itemName}\": {sub_item.itemName} Group: {group_name}")
                    continue
                except NotImplementedError:
                    self.logger.error(f"Scene name was incorrect: {item['sourceName']}. `{parent_string}` is not a valid state.")
                    continue
            scene.add_sub_item(key=status, sub_item=sub_item, group_name=group_name)
            self.logger.debug(f"Scene subitem added to {scene.itemName}: {sub_item.itemName} Group: {group_name}")
        for group_name, items in temp_statuses.items():
            for key, value in items.items():
                scene.sub_items[group_name][key].add_sub_item(UserStatus(value.itemName), value)
                self.logger.debug(f"Scene subitem added to {scene.sub_items[group_name][key].itemName}: {value.itemName} Group: {group_name}")

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
        self.logger.debug(f"Setting all {len(self.user_scenes.keys())} user to {target_state}")
        for name in self.user_scenes.keys():
            await self.set_user_to(name, target_state, only_present)

    @async_wrapped
    async def blinking_task(self, user: str) -> None:
        if self.blink_time is None or self.low_blinking_interval is None or self.high_blinking_interval is None:
            self.logger.trace(f"Tried to create blinking task for {user} when some blinking values are None")
            return
        self.logger.debug(f"Creating blinking task for {user}")
        while not self.stop_event.is_set():
            sleep_between_blinks = random.randint(self.low_blinking_interval, self.high_blinking_interval) / 1000
            self.logger.debug(f"Sleeping for {sleep_between_blinks} seconds")
            await sleep(sleep_between_blinks)
            self.logger.trace(f"Blinking task sleep finished")
            user_scene = self.user_scenes.get(user, None)
            if user_scene is None or not user_scene.enabled:
                self.logger.trace(f"User scene {user} was disabled")
                continue
            current_scene = [subitem for subitem in user_scene.current_subitems.values() if subitem.enabled][0]
            if UserStatus.Blinking not in current_scene.current_subitems.keys():
                self.logger.trace(f"User scene {user} with active scene {current_scene.itemName} has no blinking")
                continue
            await self.set_user_to(user, UserStatus(current_scene.itemName), sub_target_state=UserStatus.Blinking)
            await sleep(self.blink_time / 1000)
            if len([subitem for subitem in user_scene.current_subitems.values() if subitem.enabled]) > 0:
                self.logger.trace(f"No blinking subitems active")
                continue
            await self.set_user_to(user, UserStatus(current_scene.itemName))

    @async_wrapped
    async def set_user_to(self, name: str, target_state: UserStatus, only_present: bool = False, sub_target_state: UserStatus | None = None) -> None:
        if not self.is_connected:
            if target_state == UserStatus.Left:
                if name in self.requested_states.keys():
                    del self.requested_states[name]
                return
            self.requested_states[name] = target_state
            return
        requests = []
        self.logger.debug(f"Setting {name} user's scene to {target_state.name} with substate {sub_target_state}")
        self.current_state[name] = target_state
        scene = self.user_scenes.get(name, None)
        if scene is None or (not scene.enabled and only_present): return
        if target_state != UserStatus.Left and not scene.enabled:
            self.add_blinking_to_user(name, scene)
        elif scene.enabled and target_state == UserStatus.Left and name in self.blinking_tasks.keys():
            self.blinking_tasks[name].cancel()
            del self.blinking_tasks[name]
        scene.enabled = target_state.value != UserStatus.Left.value

        for state, scene_item in scene.current_subitems.items():
            scene_item_state = state == target_state and sub_target_state is None
            if scene_item.enabled and scene_item_state: return # Same state True, already set to that.
            if scene_item.enabled != scene_item_state:
                scene_item.enabled = scene_item_state
                requests.append(scene_item.get_request(scene.itemName, self.request_id).to_request_dict())
            # Main target handled
            for sub_state, sub_scene_item in scene_item.current_subitems.items():
                sub_scene_item_state = sub_state == sub_target_state and state == target_state
                if sub_scene_item.enabled and sub_scene_item_state: return # Same substate True, already set to that.
                sub_scene_item.enabled = sub_scene_item_state
                requests.append(sub_scene_item.get_request(scene.itemName, self.request_id).to_request_dict())

        batch_request = {
            "requestId": self.request_id,
            "executionType": 2,
            "requests": requests
        }
        await self.send(batch_request, OpCode.RequestBatch)
        await self.get_message(OpCode.RequestBatchResponse)

    async def set_group(self, name: str) -> bool:
        self.logger.debug(f"Setting {name} group")
        success = False
        for user, scene in self.user_scenes.items():
            if name in scene.group_names:
                current_state = UserStatus(self.current_state.get(user, UserStatus.Left.value))
                await self.set_user_to(user, UserStatus.Left, only_present=True)
                scene.change_group(name)
                await self.set_user_to(user, current_state, only_present=False)
                success = True
        if not success: return False
        self.current_group = name
        return True

    def get_groups(self) -> List[str]:
        tmp = {}
        for item in self.user_scenes.values():
            for group_name in item.group_names:
                tmp[group_name] = False
        return list(tmp.keys())

    def get_scene_map(self) -> dict:
        return {
            "connected": self.is_connected,
            "message_queue":self.message_queue.qsize(),
            "scenes":[{
                "name": name,
                "present": scene.enabled,
                "group": scene.current_group_name,
                "blinking":self.blinking_tasks.get(name, None) is not None,
                "all": [{
                    "name":x.itemName,
                    "enabled":x.enabled,
                    "subItems": [{
                        "name":xx.itemName,
                        "enabled":xx.enabled
                    } for kk, xx in x.current_subitems.items()]
                } for k, x in scene.current_subitems.items()]
            } for name, scene in self.user_scenes.items()]
        }
