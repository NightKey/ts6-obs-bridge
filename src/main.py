import asyncio
from collections import deque
from asyncio import AbstractEventLoop
from json import load
from typing import Tuple, List, Callable, Any, Deque, Coroutine, Dict
from os import path
import atexit

from smdb_logger import Logger, LEVEL

from modules import Settings, Status, UserStatus, WebUI, Database, OBSConnector, TeamSpeak6Connector, OBSException

DATA_FOLDER = path.join(path.abspath('.'), "data")
fp = open(path.join(DATA_FOLDER, "levels"), 'r')
LEVELS = load(fp)
fp.close()

class Main:
    settings: Settings
    status: Status
    logger: Logger
    web_ui: WebUI
    database: Database
    loop: AbstractEventLoop
    obs_connector: OBSConnector
    team_speak_6_connector: TeamSpeak6Connector
    obs_command_queue: Deque[Tuple[Callable[[...], Coroutine[Any, Any, None]], Dict[str, Any]]] = deque()

    def __init__(self, logger: Logger, loop: AbstractEventLoop):
        self.logger = logger
        self.loop = loop
        self.status = Status.StandingBy
        self.database = loop.run_until_complete(
            Database.create(
                logger=Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["database"])),
                data_path=DATA_FOLDER
            )
        )
        self.settings = loop.run_until_complete(self.database.get_settings())
        self.web_ui = WebUI(
            logger=Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["webui"])),
            get_settings_callback=self.get_settings,
            update_settings_callback=self.update_settings,
            get_state_callback=self.get_state,
            connect_obs_callback=self.connect_to_obs,
            connect_teamspeak_callback=self.connect_to_teamspeak,
            stop_all_callback=self.stop_all,
            ts_user_map_callback=self.get_ts_user_map,
            obs_scene_map_callback=self.get_obs_scene_map
        )
        self.team_speak_6_connector = TeamSpeak6Connector(
            logger=Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["teamspeak"])),
            connection_failed_callback=self.connection_failed_callback,
            user_status_changed_callback=self.user_state_changed,
            user_deafened_changed_callback=self.deafen_toggled
        )
        self.obs_connector = OBSConnector(
            logger=Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["obs"])),
            connection_failed_callback=self.connection_failed_callback
        )

    async def connect_to_teamspeak(self) -> bool:
        self.logger.info("Connecting to TeamSpeak")
        if self.team_speak_6_connector.is_connected: return True
        if self.settings.teamspeak_api is None or self.settings.teamspeak_api == "":
            auth = await self.team_speak_6_connector.request_auth(
                teamspeak_ip=self.settings.teamspeak_ip,
                teamspeak_port=self.settings.teamspeak_port
            )
            self.settings.teamspeak_api = auth
            await self.update_settings(self.settings)
        result = await self.team_speak_6_connector.connect(
            teamspeak_ip=self.settings.teamspeak_ip,
            teamspeak_port=self.settings.teamspeak_port,
            teamspeak_api=self.settings.teamspeak_api
        )
        self.status |= result
        return bool(self.status & Status.TeamSpeakReady)

    async def connect_to_obs(self) -> bool:
        self.logger.info("Connecting to OBS")
        if self.obs_connector.is_connected: return True
        result = await  self.obs_connector.connect(
            obs_ip=self.settings.obs_ip,
            obs_port=self.settings.obs_port,
            obs_password=self.settings.obs_password,
            obs_scene=self.settings.obs_scene
        )
        self.status |= result
        return bool(self.status & Status.OBSReady)

    def connection_failed_callback(self, failed_mask: Status):
        self.logger.warning(f"Connection failed {failed_mask.name}")
        self.status &= failed_mask

    def get_state(self) -> Tuple[bool, bool]:
        return bool(self.status & Status.TeamSpeakReady), bool(self.status & Status.OBSReady)

    def start_web_ui(self):
        self.web_ui.start()

    def get_settings(self) -> Settings:
        return self.settings

    async def update_settings(self, data: Settings) -> None:
        if await self.database.upsert_settings(data):
            if self.settings is None:
                self.settings = data
                return
            (reconnect_teamspeak, reconnect_obs) = self.settings.which_changed(data)
            self.settings = data
            if reconnect_obs and self.obs_connector.is_connected:
                await self.obs_connector.close()
                await self.connect_to_obs()
            if reconnect_teamspeak and self.team_speak_6_connector.is_connected:
                await self.team_speak_6_connector.close()
                await self.connect_to_teamspeak()

    async def user_state_changed(self, user: str, from_state: UserStatus, target_state: UserStatus) -> None:
        self.logger.debug(f"Change state requested for {user}")
        if not self.obs_connector.is_connected: return
        await self.obs_connector.change_state(user, from_state, target_state)

    async def deafen_toggled(self, is_deafened: bool) -> None:
        self.logger.debug("Deafen toggled")
        if not self.obs_connector.is_connected: return
        await self.obs_connector.toggle_deafen(is_deafened)

    async def stop_all(self) -> None:
        await self.obs_connector.close()
        await self.team_speak_6_connector.close()

    def close(self):
        self.loop.run_until_complete(self.stop_all())
        self.loop.run_until_complete(self.database.close())
        self.web_ui.close()

    def get_ts_user_map(self) -> List[dict]:
        return self.team_speak_6_connector.get_user_map()

    def get_obs_scene_map(self) -> dict:
        return self.obs_connector.get_scene_map()

if __name__=="__main__":
    main_logger = Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["main"]))
    main_logger.info("Starting application")
    main = Main(main_logger, asyncio.new_event_loop())
    main_logger.debug("Registering atexit")
    atexit.register(main.close)
    main.start_web_ui()
