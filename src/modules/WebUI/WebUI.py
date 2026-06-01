from typing import Callable, Tuple, Coroutine, Any, List

from smdb_logger import Logger
from smdb_web_server import HTMLServer, UrlData, Protocol, KnownError, ResponseCode
from json import loads, dumps
from os import path

from . import templates, static
from .. import TeamSpeakException, Settings, OBSException


class WebUI:
    server: HTMLServer
    logger: Logger
    get_settings_callback: Callable[[], Settings]
    update_settings_callback: Callable[[Settings], Coroutine[Any, Any, None]]
    get_state_callback: Callable[[], Tuple[bool, bool]]
    connect_obs_callback: Callable[[], Coroutine[Any, Any, bool]]
    connect_teamspeak_callback: Callable[[], Coroutine[Any, Any, bool]]
    stop_all_callback: Callable[[], Coroutine[Any, Any, None]]
    ts_user_map_callback: Callable[[], List[dict]]
    obs_scene_map_callback: Callable[[], dict]


    def __init__(
            self,
            logger: Logger,
            get_settings_callback: Callable[[], Settings],
            update_settings_callback: Callable[[Settings], Coroutine[Any, Any, None]],
            get_state_callback: Callable[[], Tuple[bool, bool]],
            connect_obs_callback: Callable[[], Coroutine[Any, Any, bool]],
            connect_teamspeak_callback: Callable[[], Coroutine[Any, Any, bool]],
            stop_all_callback: Callable[[], Coroutine[Any, Any, None]],
            ts_user_map_callback: Callable[[], List[dict]],
            obs_scene_map_callback: Callable[[], dict]
    ):
        self.logger = logger
        self.get_settings_callback = get_settings_callback
        self.update_settings_callback = update_settings_callback
        self.get_state_callback = get_state_callback
        self.connect_obs_callback = connect_obs_callback
        self.connect_teamspeak_callback = connect_teamspeak_callback
        self.stop_all_callback = stop_all_callback
        self.ts_user_map_callback = ts_user_map_callback
        self.obs_scene_map_callback = obs_scene_map_callback
        self.server = HTMLServer(host="127.0.0.1", port=12345, root_path=path.dirname(__file__), logger=logger, title="Stream Control Panel")
        # Main page
        self.server.add_url_rule("/", self.index)
        self.server.add_url_rule("/update_settings", self.update_settings, Protocol.Post)
        self.server.add_url_rule("/get_settings", self.get_settings, disable_cache=True)
        self.server.add_url_rule("/get_state", self.get_state, disable_cache=True)
        self.server.add_url_rule("/connect_obs", self.connect_obs)
        self.server.add_url_rule("/connect_teamspeak", self.connect_teamspeak)
        self.server.add_url_rule("/stop_all", self.stop_all)
        # Teamspeak
        self.server.add_url_rule("/teamspeak", self.teamspeak)
        self.server.add_url_rule("/get_teamspeak_user_map", self.ts_user_map)
        # OBS
        self.server.add_url_rule("/obs", self.obs)
        self.server.add_url_rule("/get_obs_scenes", self.obs_scene_map)


    def start(self) -> None:
        self.server.serve_forever(templates=templates.__dict__, static=static.__dict__)

    def index(self, _) -> str:
        return self.server.render_template_file(name="index.html", page_title="Stream Control Panel")

    def teamspeak(self, _) -> str:
        return self.server.render_template_file(name="teamspeak", page_title="Team Speak connector details")

    def obs(self, _) -> str:
        return self.server.render_template_file(name="obs", page_title="OBS Scene Monitor")

    def ts_user_map(self, _) -> str:
        return dumps(self.ts_user_map_callback())

    def obs_scene_map(self, _) -> str:
        return dumps(self.obs_scene_map_callback())

    async def update_settings(self, url_data: UrlData) -> str:
        await self.update_settings_callback(Settings.from_json(loads(url_data.data.decode())))
        return "{}"

    def get_settings(self, _: UrlData) -> str:
        settings = self.get_settings_callback()
        if settings is None:
            return "{}"
        return dumps(settings.to_json())

    def get_state(self, _: UrlData) -> str:
        states = self.get_state_callback()
        return dumps({"teamspeak_connected":states[0], "OBS_connected":states[1]})

    async def connect_obs(self, _: UrlData) -> str:
        try:
            return dumps({"connected":await self.connect_obs_callback()})
        except OBSException as ex:
            raise KnownError(reason=ex.message, response_code=500)

    async def connect_teamspeak(self, _: UrlData) -> str:
        try:
            return dumps({"connected":await self.connect_teamspeak_callback()})
        except TeamSpeakException as ex:
            raise KnownError(reason=ex.message, response_code=500)

    async def stop_all(self, _: UrlData) -> str:
        await self.stop_all_callback()
        return "{}"

    def close(self):
        self.server.stop()
