from smdb_db_manager import DBManager, Version
from os import path

from .. import Settings, TeamSpeakSettings, OBSSettings


class Database(DBManager):
    @property
    def current_version(self) -> Version:
        return Version(0, 0, 8)

    @DBManager.async_database_safe
    @DBManager.async_during_init
    @DBManager.async_timed
    @DBManager.fail_with_exception
    async def migrate_db(self, current: Version, target: Version) -> bool:
        if self.db is None: raise Exception("Database not initialized")
        self.keep_versioned_backup()
        version = current
        while version != target:
            if version ==  Version(0, 0, 1):
                await self.run_sql_update_script_unsafe(path.join(self.data_path, "002.sql"))
                version = Version(0, 0, 2)
            if version == Version(0, 0, 2):
                await self.run_sql_update_script_unsafe(path.join(self.data_path, "003.sql"))
                version = Version(0, 0, 3)
            if version == Version(0, 0, 3):
                await self.run_sql_update_script_unsafe(path.join(self.data_path, "004.sql"))
                version = Version(0, 0, 4)
            if version == Version(0, 0, 4):
                await self.run_sql_update_script_unsafe(path.join(self.data_path, "005.sql"))
                version = Version(0, 0, 5)
            if version == Version(0, 0, 5):
                await self.run_sql_update_script_unsafe(path.join(self.data_path, "006.sql"))
                version = Version(0, 0, 6)
            if version == Version(0, 0, 6):
                await self.run_sql_update_script_unsafe(path.join(self.data_path, "007.sql"))
                version = Version(0, 0, 7)
            if version == Version(0, 0, 7):
                await self.run_sql_update_script_unsafe(path.join(self.data_path, "008.sql"))
                version = Version(0, 0, 8)
        return True

    @DBManager.async_database_safe
    @DBManager.async_during_init
    @DBManager.async_timed
    @DBManager.fail_with_exception
    async def init_db(self) -> None:
        await self.run_sql_update_script_unsafe(path.join(self.data_path, "create.sql"))

    @DBManager.async_database_safe
    @DBManager.with_fail_value(None)
    @DBManager.async_timed
    async def get_settings(self) -> Settings | None:
        teamspeak = list(
            await self.db.execute_fetchall(
                f"""SELECT ip,
                           port,
                           api,
                           user_mute_behavior
                    FROM teamspeak_settings
                    ORDER BY id ASC
                    LIMIT 1;
                """
            )
        )
        obs = list(
            await self.db.execute_fetchall(
                f"""SELECT ip,
                           port,
                           password,
                           low_blink_interval,
                           high_blink_interval,
                           blink_time,
                           blink_enabled
                    FROM obs_settings
                    ORDER BY id ASC
                    LIMIT 1;
                """
            )
        )
        general = list(
            await self.db.execute_fetchall(
                f"""SELECT autoconnect,
                           host,
                           port,
                           speak_start_animation_enabled,
                           speak_end_animation_enabled
                    FROM general_settings
                    ORDER BY id ASC
                    LIMIT 1;
                """
            )
        )
        if len(general) == 0 or len(obs) == 0 or len(teamspeak) == 0:
            self.logger.warning("No settings found")
            return None
        teamspeak = teamspeak[0]
        obs = obs[0]
        general = general[0]
        teamspeak_settings = TeamSpeakSettings(
            ip=teamspeak[0],
            port=teamspeak[1],
            api=teamspeak[2],
            user_mute_behavior=teamspeak[3]
        )
        obs_settings = OBSSettings(
            ip=obs[0],
            port=obs[1],
            password=obs[2],
            low_blink_interval=obs[3],
            high_blink_interval=obs[4],
            blink_time=obs[5],
            blink_enabled=obs[6]
        )
        return Settings(
            teamspeak=teamspeak_settings,
            obs=obs_settings,
            autoconnect=general[0],
            host=general[1],
            port=general[2],
            speak_start_animation_enabled=general[3],
            speak_end_animation_enabled=general[4],
        )

    @DBManager.async_database_safe
    @DBManager.async_timed
    async def upsert_settings(self, settings: Settings) -> bool:
        if settings.teamspeak is None or settings.obs is None: return False
        await self.db.execute(
            """INSERT OR REPLACE INTO general_settings
                   (id, autoconnect, host, port,
                    speak_start_animation_enabled, speak_end_animation_enabled)
               VALUES (1, ?, ?, ?, ?, ?)""",
            (
                settings.autoconnect,
                settings.host,
                settings.port,
                settings.speak_start_animation_enabled,
                settings.speak_end_animation_enabled,
            ),
        )
        await self.db.execute(
            """INSERT OR REPLACE INTO teamspeak_settings
                   (id, ip, port, api, user_mute_behavior)
               VALUES (1, ?, ?, ?, ?)""",
            (
                settings.teamspeak.ip,
                settings.teamspeak.port,
                settings.teamspeak.api,
                settings.teamspeak.user_mute_behavior,
            ),
        )
        await self.db.execute(
            """INSERT OR REPLACE INTO obs_settings
                   (id, ip, port, password,
                    low_blink_interval, high_blink_interval, blink_time, blink_enabled)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?)""",
            (
                settings.obs.ip,
                settings.obs.port,
                settings.obs.password,
                settings.obs.low_blink_interval,
                settings.obs.high_blink_interval,
                settings.obs.blink_time,
                settings.obs.blink_enabled,
            ),
        )
        await self.db.commit()
        return True
