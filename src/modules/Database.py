from smdb_db_manager import DBManager, Version

from . import Settings, TeamSpeakSettings, OBSSettings


class Database(DBManager):
    @property
    def current_version(self) -> Version:
        return Version(0, 0, 5)

    @DBManager.async_database_safe
    @DBManager.async_during_init
    @DBManager.async_timed
    @DBManager.fail_with_exception
    async def migrate_db(self, current: Version, target: Version) -> bool:
        version = current
        while version != target:
            if version ==  Version(0, 0, 1):
                await self.db.execute(
                    """ALTER TABLE settings ADD COLUMN autoconnect INTEGER NOT NULL DEFAULT 0;"""
                )
                await self.db.commit()
                version = Version(0, 0, 2)
            if version == Version(0, 0, 2):
                await self.db.execute(
                    """ALTER TABLE settings ADD COLUMN host TEXT DEFAULT '127.0.0.1';"""
                )
                await self.db.execute(
                    """ALTER TABLE settings ADD COLUMN port INTEGER DEFAULT 12345;"""
                )
                await self.db.commit()
                version = Version(0, 0, 3)
            if version == Version(0, 0, 3):
                await self.db.execute(
                    """ALTER TABLE settings DROP COLUMN obs_scene"""
                )
                await self.db.commit()
                version = Version(0, 0, 4)
            if version == Version(0, 0, 4):
                await self.db.execute(
                    """ALTER TABLE settings ADD COLUMN low_blink_interval INTEGER DEFAULT 1000;"""
                )
                await self.db.execute(
                    """ALTER TABLE settings ADD COLUMN high_blink_interval INTEGER DEFAULT 3000;"""
                )
                await self.db.execute(
                    """ALTER TABLE settings ADD COLUMN blink_time INTEGER DEFAULT 150;"""
                )
                await self.db.execute(
                    """ALTER TABLE settings ADD COLUMN blink_enabled INTEGER DEFAULT 0;"""
                )
                await self.db.commit()
                version = Version(0, 0, 5)
        return True

    @DBManager.async_database_safe
    @DBManager.async_during_init
    @DBManager.async_timed
    @DBManager.fail_with_exception
    async def init_db(self) -> None:
        await self.db.execute(
            f"""
            CREATE TABLE IF NOT EXISTS settings (
                teamspeak_ip TEXT NOT NULL UNIQUE,
                teamspeak_port INTEGER NOT NULL,
                teamspeak_api TEXT NOT NULL,
                obs_ip TEXT NOT NULL UNIQUE,
                obs_port INTEGER NOT NULL,
                obs_password TEXT NOT NULL,
                autoconnect INTEGER DEFAULT 0,
                host TEXT DEFAULT '127.0.0.1',
                port INTEGER DEFAULT 12345,
                low_blink_interval INTEGER DEFAULT 0,
                high_blink_interval INTEGER DEFAULT 0,
                blink_time INTEGER DEFAULT 0,
                blink_enabled INTEGER DEFAULT 0
            ) STRICT;
            """
        )
        await self.db.commit()

    @DBManager.async_database_safe
    @DBManager.with_fail_value(None)
    @DBManager.async_timed
    async def get_settings(self) -> Settings | None:
        result = await self.db.execute_fetchall(
            f"""SELECT teamspeak_ip, teamspeak_port, teamspeak_api, obs_ip, obs_port, obs_password, low_blink_interval, high_blink_interval, blink_time, blink_enabled, autoconnect, host, port FROM settings"""
        )
        if len(result) == 0:
            self.logger.warning("No settings found")
            return None
        settings = result[0]
        teamspeak_settings = TeamSpeakSettings(
            ip=settings[0],
            port=settings[1],
            api=settings[2]
        )
        obs_settings = OBSSettings(
            ip=settings[3],
            port=settings[4],
            password=settings[5],
            low_blink_interval=settings[6],
            high_blink_interval=settings[7],
            blink_time=settings[8],
            blink_enabled=settings[9]
        )
        return Settings(
            teamspeak=teamspeak_settings,
            obs=obs_settings,
            autoconnect=settings[10],
            host=settings[11],
            port=settings[12]
        )

    @DBManager.async_database_safe
    @DBManager.async_timed
    async def upsert_settings(self, settings: Settings) -> bool:
        if settings.teamspeak is None or settings.obs is None: return False
        await self.db.execute(
            f"""INSERT OR REPLACE INTO settings (teamspeak_ip, teamspeak_port, teamspeak_api, obs_ip, obs_port, obs_password, low_blink_interval, high_blink_interval, blink_time, blink_enabled, autoconnect, host, port)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                settings.teamspeak.ip,
                settings.teamspeak.port,
                settings.teamspeak.api,
                settings.obs.ip,
                settings.obs.port,
                settings.obs.password,
                settings.obs.low_blink_interval,
                settings.obs.high_blink_interval,
                settings.obs.blink_time,
                settings.obs.blink_enabled,
                settings.autoconnect,
                settings.host,
                settings.port
            )
        )
        await self.db.commit()
        return True
