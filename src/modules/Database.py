from smdb_db_manager import DBManager, Version

from . import Settings


class Database(DBManager):
    @property
    def current_version(self) -> Version:
        return Version(0, 0, 4)

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
                port INTEGER DEFAULT 12345
            ) STRICT;
            """
        )
        await self.db.commit()

    @DBManager.async_database_safe
    @DBManager.with_fail_value(None)
    @DBManager.async_timed
    async def get_settings(self) -> Settings | None:
        result = await self.db.execute_fetchall(
            f"""SELECT teamspeak_ip, teamspeak_port, teamspeak_api, obs_ip, obs_port, obs_password, autoconnect, host, port FROM settings"""
        )
        if len(result) == 0: return None
        return Settings(
            teamspeak_ip=result[0][0],
            teamspeak_port=result[0][1],
            teamspeak_api=result[0][2],
            obs_ip=result[0][3],
            obs_port=result[0][4],
            obs_password=result[0][5],
            autoconnect=result[0][6],
            host=result[0][7],
            port=result[0][8]
        )

    @DBManager.async_database_safe
    @DBManager.async_timed
    async def upsert_settings(self, settings: Settings) -> bool:
        await self.db.execute(
            f"""INSERT OR REPLACE INTO settings (teamspeak_ip, teamspeak_port, teamspeak_api, obs_ip, obs_port, obs_password, autoconnect, host, port)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                settings.teamspeak_ip,
                settings.teamspeak_port,
                settings.teamspeak_api,
                settings.obs_ip,
                settings.obs_port,
                settings.obs_password,
                settings.autoconnect,
                settings.host,
                settings.port
            )
        )
        await self.db.commit()
        return True
