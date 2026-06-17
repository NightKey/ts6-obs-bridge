import asyncio
from asyncio import sleep
from json import load
from threading import Thread
from typing import Tuple
from os import path
import time
import atexit

from smdb_db_manager import Version
from smdb_logger import Logger, LEVEL

from modules import Settings, UserStatus, WebUI, Database, OBSConnector, TeamSpeak6Connector, OBSException, \
    TeamSpeakException, show_open_calls

class Bridge:
    settings: Settings
    logger: Logger
    web_ui: WebUI
    database: Database
    obs_connector: OBSConnector
    team_speak_6_connector: TeamSpeak6Connector
    version: str
    stop_event: asyncio.Event = asyncio.Event()
    closed: bool = False

    def __init__(self, logger: Logger, version: str):
        loop = asyncio.new_event_loop()
        self.logger = logger
        self.version = version
        self.database = loop.run_until_complete(
            Database.create(
                logger=Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["database"])),
                data_path=DATA_FOLDER,
                version=Version(0, 0, 2)
            )
        )
        self.settings = loop.run_until_complete(self.database.get_settings())
        self.web_ui = WebUI(
            logger=Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["webui"])),
            get_settings_callback=self.get_settings,
            update_settings_callback=self.update_settings,
            get_state_callback=self.get_state,
            connect_all_callback=self.connect_all,
            connect_obs_callback=self.connect_to_obs,
            connect_teamspeak_callback=self.connect_to_teamspeak,
            stop_all_callback=self.stop_all,
            ts_user_map_callback=self.get_ts_user_map,
            obs_scene_map_callback=self.get_obs_scene_map,
            re_init_obs_callback=self.re_init_obs,
            toggle_autoconnect_callback=self.toggle_autoconnect,
            version=self.version
        )
        self.obs_connector = OBSConnector(
            logger=Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["obs"]))
        )
        self.team_speak_6_connector = TeamSpeak6Connector(
            logger=Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["teamspeak"])),
            version=self.version,
            user_status_changed_callback=self.user_state_changed,
            user_deafened_changed_callback=self.deafen_toggled
        )

    def connect_all(self) -> None:
        if self.stop_event.is_set():
            self.logger.debug("Resetting stop event")
            self.stop_event.clear()
            self.logger.debug("Starting auto connect")
            Thread(target=self.autoconnect, name="Auto connect loop").start()

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
        return await self.team_speak_6_connector.connect(
            teamspeak_ip=self.settings.teamspeak_ip,
            teamspeak_port=self.settings.teamspeak_port,
            teamspeak_api=self.settings.teamspeak_api
        )

    async def connect_to_obs(self) -> bool:
        self.logger.info("Connecting to OBS")
        if self.obs_connector.is_connected: return True
        return await  self.obs_connector.connect(
            obs_ip=self.settings.obs_ip,
            obs_port=self.settings.obs_port,
            obs_password=self.settings.obs_password,
            obs_scene=self.settings.obs_scene
        )

    async def re_init_obs(self) -> None:
        await self.obs_connector.re_init_obs()

    def get_state(self) -> Tuple[bool, bool]:
        return bool(self.team_speak_6_connector.is_connected), bool(self.obs_connector.is_connected)

    def start(self):
        self.logger.trace(f"Current settings: {self.settings}")
        if self.settings and self.settings.autoconnect:
            Thread(target=self.autoconnect, name="Auto connect loop").start()
        self.logger.info("Serving webUI at http://127.0.0.1:12345")
        self.web_ui.start()
        show_open_calls(self.logger.trace)
        while True:
            try:
                time.sleep(0.5)
            except KeyboardInterrupt:
                self.close()
                break

    def autoconnect(self) -> None:
        if not self.settings or not self.settings.autoconnect: return
        self.logger.debug("Starting auto connect loop")
        asyncio.new_event_loop().run_until_complete(self.autoconnect_loop())

    async def autoconnect_loop(self) -> None:
        while not self.stop_event.is_set() and self.settings and self.settings.autoconnect:
            try:
                self.logger.trace(f"Checking if team speak is connected {self.team_speak_6_connector.is_connected}")
                if not self.team_speak_6_connector.is_connected:
                     await self.connect_to_teamspeak()
            except TeamSpeakException as tse:
                self.logger.error("Team Speak failed to connect", tse)
            except ConnectionRefusedError:
                pass
            try:
                self.logger.trace(f"Checking if OBS is connected {self.team_speak_6_connector.is_connected}")
                if not self.obs_connector.is_connected:
                    await self.connect_to_obs()
            except OBSException as oe:
                self.logger.error("OBS failed to connect", oe)
            except ConnectionRefusedError:
                pass
            await sleep(5)
        await sleep(10)

    def get_settings(self) -> Settings:
        return self.settings

    async def toggle_autoconnect(self, value: bool) -> None:
        self.logger.debug(f"Toggling auto connect to {value}")
        self.settings.autoconnect = value
        self.logger.trace("Updating settings")
        await self.update_settings(self.settings)
        if self.settings.autoconnect:
            Thread(target=self.autoconnect, name="Auto connect loop").start()

    async def update_settings(self, data: Settings) -> None:
        if await self.database.upsert_settings(data):
            if self.settings is None:
                self.settings = data
                return
            (reconnect_teamspeak, reconnect_obs) = self.settings.which_changed(data)
            self.settings = data
            if reconnect_obs and self.obs_connector.is_connected:
                self.obs_connector.close()
                await self.connect_to_obs()
            if reconnect_teamspeak and self.team_speak_6_connector.is_connected:
                self.team_speak_6_connector.close()
                await self.connect_to_teamspeak()

    async def user_state_changed(self, user: str, target_state: UserStatus) -> None:
        self.logger.debug(f"Change state requested for {user}")
        await self.obs_connector.set_user_to(user, target_state)

    async def deafen_toggled(self, is_deafened: bool) -> None:
        self.logger.debug("Deafen toggled")
        await self.obs_connector.toggle_deafen(is_deafened)

    def stop_all(self) -> None:
        self.stop_event.set()
        self.logger.trace("Stop event set")
        self.obs_connector.close()
        self.logger.trace("OBS close called")
        self.team_speak_6_connector.close()
        self.logger.trace("TS6 close called")

    def close(self):
        if self.closed: return
        self.logger.trace("Close called")
        loop = asyncio.new_event_loop()
        self.stop_all()
        loop.run_until_complete(self.database.close())
        self.logger.trace("Database close called")
        self.web_ui.close()
        self.logger.trace("WebUI close called")
        self.closed = True

    def get_ts_user_map(self) -> dict:
        return self.team_speak_6_connector.get_user_map()

    def get_obs_scene_map(self) -> dict:
        return self.obs_connector.get_scene_map()

if __name__=="__main__":
    DATA_FOLDER = path.join(path.abspath('.'), "data")
    fp = open(path.join(DATA_FOLDER, "levels"), 'r')
    LEVELS = load(fp)
    fp.close()
    fp = open(path.join(DATA_FOLDER, 'version'), 'r')
    VERSION = fp.read()
    fp.close()

    main_logger = Logger(log_to_console=True, use_caller_name=True, use_file_names=True, level=LEVEL.from_string(LEVELS["main"]))
    main_logger.info(f"Starting application version {VERSION}")
    main = Bridge(main_logger, VERSION)
    main_logger.debug("Registering atexit")
    atexit.register(main.close)
    main.start()
    main_logger.debug("Finished")
    show_open_calls(main_logger.trace)
