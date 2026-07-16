from asyncio import Event, timeout, create_task, Lock
from typing import Callable, Dict, List, Coroutine, Any

from websockets import connect, ClientConnection, ConnectionClosedOK, ConnectionClosedError, State
from json import loads, dumps
from smdb_logger import Logger

from . import TeamSpeakException, ClientInfo
from .. import UserStatus, BaseConnector, async_wrapped, async_sync, TeamSpeakSettings


class TeamSpeak6Connector(BaseConnector):
    __logger: Logger
    sync_lock = Lock()
    user_status_changed_callback: Callable[[str, UserStatus], Coroutine[Any, Any, None]]
    user_deafened_changed_callback: Callable[[bool], Coroutine[Any, Any, None]]
    user: ClientInfo
    websocket: ClientConnection | None = None
    stop_event: Event = Event()
    stopped: Event = Event()
    user_client_info_map: Dict[int, ClientInfo] = {}
    version: str

    @property
    def is_connected(self) -> bool:
        return self.websocket is not None and self.websocket.state == State.OPEN

    @property
    def logger(self) -> Logger:
        return self.__logger

    @property
    def name(self) -> str:
        return "TeamSpeak6Connector"

    def __init__(
            self,
            logger: Logger,
            version: str,
            user_status_changed_callback: Callable[[str, UserStatus], Coroutine[Any, Any, None]],
            user_deafened_changed_callback: Callable[[bool], Coroutine[Any, Any, None]]
    ):
        self.__logger = logger
        self.version = version
        self.user_status_changed_callback = user_status_changed_callback
        self.user_deafened_changed_callback = user_deafened_changed_callback
        self.stopped.set()

    def evaluate_client_info(self, client_info: ClientInfo | None, user_channel: int | None = None) -> UserStatus | None:
        if client_info is None or client_info.name is None: return None
        if user_channel is None: user_channel = self.user.channel_id
        if client_info.is_muted or user_channel != client_info.channel_id: return UserStatus.Left
        if client_info.is_muted_by_user: return UserStatus.Muted
        if client_info.is_talking: return UserStatus.Speaking
        return UserStatus.Quiet

    @async_wrapped
    async def request_auth(self, settings: TeamSpeakSettings) -> str:
        self.logger.info("Requesting authentication from user")
        auth_request = {
            "type": "auth",
            "payload": {
                "identifier": "TeamSpeak6-OBS-Bridge",
                "version": self.version,
                "name": "TeamSpeak6 to OBS Bridge",
                "description": "A stream helper with TeamSpeak6 and OBS Studio integration.",
                "content": {
                    "apiKey": ""
                }
            }
        }
        websocket = await connect(f"ws://{settings.ip}:{settings.port}")
        await websocket.send(dumps(auth_request))
        response = loads(await websocket.recv())
        await websocket.close()
        if response["status"]["message"] != "ok":
            raise TeamSpeakException(f"Authentication request failed. reason: {response['status']['message']}")
        self.logger.debug("API key retrieved")
        api_key = response["payload"]["apiKey"]
        return api_key

    @async_wrapped
    async def connect(self, settings: TeamSpeakSettings) -> bool:
        self.stop_event.clear()
        self.logger.info("Connecting ot teamspeak")
        auth_request = {
            "type": "auth",
            "payload": {
                "identifier": "TeamSpeak6-OBS-Bridge",
                "version": self.version,
                "name": "TeamSpeak6 to OBS Bridge",
                "description": "A stream helper with TeamSpeak6 and OBS Studio integration.",
                "content": {
                    "apiKey": settings.api
                }
            }
        }
        websocket = await connect(f"ws://{settings.ip}:{settings.port}")
        await websocket.send(dumps(auth_request))
        response = loads(await websocket.recv())
        if response["status"]["message"] != "ok":
            raise TeamSpeakException(f"Authentication request failed. reason: {response['status']['message']}")
        self.logger.debug("Authenticated")
        self.logger.trace(f"Response: {response}")
        self.websocket = websocket
        if len(response["payload"]["connections"]) == 0:
            raise TeamSpeakException(f"Could not determine user. Please connect to a server.")
        await self.load_clients_present(response["payload"]["connections"][0]["clientId"],  response["payload"]["connections"][0]["clientInfos"])
        self.logger.debug(f"User id: {self.user.id}")
        self.stopped.clear()
        create_task(self.retrieve_loop(), name="TS6 retrieve task")
        return True

    @async_wrapped
    async def load_clients_present(self, user_id: int, clients: List[dict]) -> None:
        self.logger.info("Loading clients present")
        self.logger.debug(f"Clients count: {len(clients)}")
        for client in clients:
            client_info = ClientInfo.from_dict(client)
            self.logger.trace(f"Client info: {client_info}")
            if client_info.id == user_id:
                self.user = client_info
                continue
            self.user_client_info_map[client_info.id] = client_info
            await self.user_state_changed(client_info.name, self.evaluate_client_info(client_info))

    def close(self) -> None:
        if self.stop_event.is_set(): return
        self.logger.info("Closing TeamSpeak6 connection")
        self.stop_event.set()

    @async_wrapped
    async def __cleanup(self) -> None:
        self.logger.info("Cleanup")
        await self.websocket.close()
        self.user_client_info_map.clear()
        self.websocket = None
        self.stopped.set()

    @async_wrapped
    async def retrieve_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                async with timeout(0.5):
                    message = loads(await self.websocket.recv())
                    self.logger.trace(f"New message with type: {message['type']}")
                    if message["type"] == "clientPropertiesUpdated":
                        await self.client_property_updated(message["payload"])
                    elif message["type"] == "talkStatusChanged":
                        await self.talking_status_changed(message["payload"])
                    elif message["type"] == "clientChannelGroupChanged":
                        await self.client_channel_group_changed(message["payload"])
                    elif message["type"] == "clientMoved":
                        await self.client_moved(message["payload"])
                self.logger.heartbeat(".")
            except TimeoutError:
                pass
            except ConnectionClosedOK:
                self.logger.info("Connection closed by server without error")
                self.stop_event.set()
            except ConnectionClosedError as cce:
                self.logger.error("Connection closed with error", cce)
                self.stop_event.set()
            except Exception as ex:
                self.logger.error("Error during retrieving message", ex)
        await self.__cleanup()

    @async_wrapped
    @async_sync
    async def client_property_updated(self, message: dict) -> None:
        self.logger.debug("Processing clientPropertiesUpdated message")
        client_id = message["clientId"]
        new_client_info = ClientInfo.from_dict(message, client_id)
        if client_id == self.user.id:
            await self.user_deafened_changed(new_client_info.is_deafened)
            return
        client_info = self.user_client_info_map.get(new_client_info.id, None)
        if client_info is None:
            client_info = new_client_info
        else:
            client_info = client_info.merge(new_client_info)
        self.user_client_info_map[new_client_info.id] = client_info
        new_status = self.evaluate_client_info(client_info)
        self.logger.trace(
            f"clientPropertiesUpdated: Calling user_state_changed for user {client_info.name} mew status {new_status}")
        await self.user_state_changed(client_info.name, new_status)
        self.user_client_info_map[client_info.id] = client_info

    @async_wrapped
    @async_sync
    async def talking_status_changed(self, message: dict) -> None:
        self.logger.debug("Processing talkStatusChanged message")
        self.logger.trace(str(message))
        talker_id = message["clientId"]
        is_talking = message["status"] == 1
        if talker_id == self.user.id:
            self.logger.debug("Talker was user")
            return
        old_info = self.user_client_info_map[talker_id]
        old_status = self.evaluate_client_info(old_info)
        if old_status is not None and old_status.name == UserStatus.Left.name:
            self.logger.info(f"Ignoring state change for {old_info.name} from Left")
            return
        current_status = self.evaluate_client_info(old_info)
        if not current_status or current_status.name == UserStatus.Left.name: return
        new_status = UserStatus.Speaking if is_talking else UserStatus.Quiet
        if current_status.name == UserStatus.Muted.name and new_status.name == UserStatus.Quiet.name: return
        self.logger.trace(f"talkStatusChanged: Calling user_state_changed for user {old_info.name} old status {current_status} mew status {new_status}")
        await self.user_state_changed(old_info.name, new_status)
        old_info.is_talking = is_talking
        if old_info.is_talking:
            old_info.is_muted_by_user = False
            old_info.is_muted = False
        self.user_client_info_map[old_info.id] = old_info

    @async_wrapped
    @async_sync
    async def client_channel_group_changed(self, message: dict) -> None:
        new_channel_id = message["channelId"]
        client_id = message["clientId"]
        if client_id != self.user.id: return
        for client_id, client_info in self.user_client_info_map.items():
            self.logger.trace(
                f"clientChannelGroupChanged: Calling user_state_changed for user {client_info.name} old status {self.evaluate_client_info(client_info)} mew status {UserStatus.Left if client_info.channel_id != new_channel_id else UserStatus.Quiet}")
            await self.user_state_changed(
                client_info.name,
                self.evaluate_client_info(client_info, new_channel_id)
            )
        self.user.channel_id = new_channel_id

    @async_wrapped
    @async_sync
    async def client_moved(self, message: dict) -> None:
        client_id = message["clientId"]
        new_channel_id = message["newChannelId"]
        if client_id == self.user.id:
            for client_id, client_info in self.user_client_info_map.items():
                self.logger.trace(
                    f"clientMoved: Calling user_state_changed for user {client_info.name} old status {self.evaluate_client_info(client_info)} mew status {UserStatus.Left if client_info.channel_id != new_channel_id else UserStatus.Quiet}")
                await self.user_state_changed(
                    client_info.name,
                    self.evaluate_client_info(client_info, new_channel_id)
                )
            self.user.channel_id = new_channel_id
        else:
            client_info = self.user_client_info_map.get(client_id, None)
            if client_info is None:
                self.user_client_info_map[client_id] = ClientInfo(
                    id=client_id,
                    name="Unknown User",
                    is_talking=None,
                    is_muted=None,
                    is_deafened=None,
                    is_muted_by_user=None,
                    channel_id=new_channel_id,
                )
                return
            self.logger.trace(f"clientMoved: Calling user_state_changed for user {client_info.name} old status {self.evaluate_client_info(client_info)} mew status {UserStatus.Left if client_info.channel_id != new_channel_id else UserStatus.Quiet}")
            client_info = client_info.with_new_channel(new_channel_id)
            if new_channel_id == 0:
                del self.user_client_info_map[client_info.id]
            else:
                self.user_client_info_map[client_info.id] = client_info
            await self.user_state_changed(
                client_info.name,
                self.evaluate_client_info(client_info)
            )

    @async_wrapped
    async def user_state_changed(self, user_name: str, new_status: UserStatus | None) -> None:
        if new_status is None: return
        self.logger.debug(f"User {user_name} status {new_status}")
        if not self.user.is_deafened: await self.user_status_changed_callback(user_name, new_status)

    @async_wrapped
    async def user_deafened_changed(self, status: bool | None) -> None:
        if status is None: return
        await self.user_deafened_changed_callback(status)

    def get_user_map(self) -> dict:
        return {"connected": self.is_connected, "users": [{"id":x.id, "name":x.name, "status":self.evaluate_client_info(x).value} for x in self.user_client_info_map.values()]}
