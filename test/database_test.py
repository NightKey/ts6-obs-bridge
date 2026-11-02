import asyncio
import inspect
import shutil
from pathlib import Path

import pytest

from src.modules import Database, Settings, TeamSpeakSettings, OBSSettings
from smdb_logger import Logger, LEVEL
from smdb_db_manager import DBManager

# Same folder as path.join("..", "src", "data", "sqls"), but anchored to this
# file instead of the current working directory, so the tests work no matter
# where pytest is started from.
SQL_FOLDER = (Path(__file__).resolve().parent / ".." / "src" / "data" / "sqls").resolve()


# --------------------------------------------------------------------------- #
# Test-only subclass: exposes raw SQL access through the decorator that
# guards the db attribute.
# --------------------------------------------------------------------------- #

class TestableDatabase(Database):
    __test__ = False  # stop pytest from trying to collect this as a test class

    @DBManager.async_database_safe
    async def fetch_all(self, sql: str):
        return list(await self.db.execute_fetchall(sql))

    @DBManager.async_database_safe
    async def execute_and_commit(self, sql: str):
        await self.db.execute(sql)
        await self.db.commit()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def make_settings(**overrides) -> Settings:
    """Settings with non-default values, so round-trips are meaningful."""
    values = dict(
        teamspeak=TeamSpeakSettings(
            ip="10.0.0.5",
            port=25639,
            api="ts-api-key",
            user_mute_behavior=0,
        ),
        obs=OBSSettings(
            ip="10.0.0.6",
            port=4456,
            password="obs-secret",
            low_blink_interval=2,
            high_blink_interval=7,
            blink_time=150,
            blink_enabled=1,
        ),
        autoconnect=1,
        host="0.0.0.0",
        port=54321,
        speak_start_animation_enabled=1,
        speak_end_animation_enabled=1,
    )
    values.update(overrides)
    return Settings(**values)


def assert_settings_equal(actual: Settings, expected: Settings) -> None:
    """Field-by-field comparison so a failure names the differing value."""
    assert actual.autoconnect == expected.autoconnect
    assert actual.host == expected.host
    assert actual.port == expected.port
    assert actual.speak_start_animation_enabled == expected.speak_start_animation_enabled
    assert actual.speak_end_animation_enabled == expected.speak_end_animation_enabled

    assert actual.teamspeak.ip == expected.teamspeak.ip
    assert actual.teamspeak.port == expected.teamspeak.port
    assert actual.teamspeak.api == expected.teamspeak.api
    assert actual.teamspeak.user_mute_behavior == expected.teamspeak.user_mute_behavior

    assert actual.obs.ip == expected.obs.ip
    assert actual.obs.port == expected.obs.port
    assert actual.obs.password == expected.obs.password
    assert actual.obs.low_blink_interval == expected.obs.low_blink_interval
    assert actual.obs.high_blink_interval == expected.obs.high_blink_interval
    assert actual.obs.blink_time == expected.obs.blink_time
    assert actual.obs.blink_enabled == expected.obs.blink_enabled


def create_database(loop, data_path: Path) -> TestableDatabase:
    return loop.run_until_complete(
        TestableDatabase.create(
            logger=Logger(
                log_to_console=False,
                level=LEVEL.INFO,
                max_caller_chain_size=5,
                max_logfile_lifetime=2,
            ),
            data_path=str(data_path),
        )
    )


async def close_database(database: Database) -> None:
    """Best-effort cleanup; only calls close() if your DBManager has one."""
    close = getattr(database, "close", None)
    if close is not None:
        result = close()
        if inspect.isawaitable(result):
            await result


def assert_isolated(loop, database: TestableDatabase, tmp_path: Path) -> None:
    """Safety net: fails loudly if the database file is not inside tmp_path,
    so a test can never run against (or modify) the production database."""
    rows = loop.run_until_complete(database.fetch_all("PRAGMA database_list"))
    files = [row[2] for row in rows if row[1] == "main"]
    assert files, "could not determine the database file"
    db_file = files[0]
    # An empty path means an in-memory database, which is also isolated.
    assert db_file == "" or Path(db_file).resolve().is_relative_to(tmp_path.resolve()), (
        f"Test database is not isolated! Using: {db_file}"
    )


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def loop():
    event_loop = asyncio.new_event_loop()
    yield event_loop
    event_loop.close()


@pytest.fixture
def data_path(tmp_path) -> Path:
    """Fresh data folder containing only the SQL scripts.
    Copying only *.sql means an existing production .db file is never copied."""
    assert SQL_FOLDER.is_dir(), f"SQL script folder not found: {SQL_FOLDER}"
    target = tmp_path / "data"
    target.mkdir()
    for script in SQL_FOLDER.glob("*.sql"):
        shutil.copy(script, target / script.name)
    return target


@pytest.fixture
def database(loop, data_path, tmp_path):
    db = create_database(loop, data_path)
    assert_isolated(loop, db, tmp_path)
    yield db
    loop.run_until_complete(close_database(db))


# --------------------------------------------------------------------------- #
# Fresh database
# --------------------------------------------------------------------------- #

def test_fresh_database_has_expected_tables(loop, database):
    rows = loop.run_until_complete(
        database.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table'")
    )
    tables = {row[0] for row in rows}
    assert {"general_settings", "teamspeak_settings", "obs_settings"} <= tables
    assert "settings" not in tables  # the old combined table must not exist


def test_fresh_database_has_no_settings(loop, database):
    assert loop.run_until_complete(database.get_settings()) is None
    for table in ("general_settings", "teamspeak_settings", "obs_settings"):
        rows = loop.run_until_complete(database.fetch_all(f"SELECT COUNT(*) FROM {table}"))
        assert rows[0][0] == 0, f"{table} should start empty"


# --------------------------------------------------------------------------- #
# upsert_settings
# --------------------------------------------------------------------------- #

def test_upsert_returns_true(loop, database):
    assert loop.run_until_complete(database.upsert_settings(make_settings())) is True


def test_upsert_then_get_round_trip(loop, database):
    expected = make_settings()
    loop.run_until_complete(database.upsert_settings(expected))

    actual = loop.run_until_complete(database.get_settings())

    assert actual is not None
    assert_settings_equal(actual, expected)


def test_upsert_overwrites_instead_of_adding_rows(loop, database):
    first = make_settings()
    second = make_settings(
        teamspeak=TeamSpeakSettings(
            ip="192.168.1.10", port=1111, api="new-key", user_mute_behavior=1
        ),
        obs=OBSSettings(
            ip="192.168.1.11",
            port=2222,
            password="new-password",
            low_blink_interval=0,
            high_blink_interval=0,
            blink_time=0,
            blink_enabled=0,
        ),
        autoconnect=0,
        host="127.0.0.1",
        port=12345,
        speak_start_animation_enabled=0,
        speak_end_animation_enabled=0,
    )

    loop.run_until_complete(database.upsert_settings(first))
    loop.run_until_complete(database.upsert_settings(second))

    actual = loop.run_until_complete(database.get_settings())
    assert actual is not None
    assert_settings_equal(actual, second)

    for table in ("general_settings", "teamspeak_settings", "obs_settings"):
        rows = loop.run_until_complete(database.fetch_all(f"SELECT COUNT(*) FROM {table}"))
        assert rows[0][0] == 1, f"{table} should contain exactly one row"


def test_upsert_is_idempotent(loop, database):
    settings = make_settings()
    for _ in range(3):
        assert loop.run_until_complete(database.upsert_settings(settings)) is True

    actual = loop.run_until_complete(database.get_settings())
    assert actual is not None
    assert_settings_equal(actual, settings)


@pytest.mark.parametrize("missing", ["teamspeak", "obs"])
def test_upsert_returns_false_if_a_section_is_missing(loop, database, missing):
    settings = make_settings(**{missing: None})

    assert loop.run_until_complete(database.upsert_settings(settings)) is False
    # Nothing must have been written.
    assert loop.run_until_complete(database.get_settings()) is None
    for table in ("general_settings", "teamspeak_settings", "obs_settings"):
        rows = loop.run_until_complete(database.fetch_all(f"SELECT COUNT(*) FROM {table}"))
        assert rows[0][0] == 0, f"{table} should still be empty"


def test_each_table_receives_its_own_values(loop, database):
    """Checks the split itself: every value ends up in the correct table."""
    loop.run_until_complete(database.upsert_settings(make_settings()))

    general = loop.run_until_complete(database.fetch_all(
        "SELECT autoconnect, host, port, speak_start_animation_enabled, "
        "speak_end_animation_enabled FROM general_settings"
    ))[0]
    teamspeak = loop.run_until_complete(database.fetch_all(
        "SELECT ip, port, api, user_mute_behavior FROM teamspeak_settings"
    ))[0]
    obs = loop.run_until_complete(database.fetch_all(
        "SELECT ip, port, password, low_blink_interval, high_blink_interval, "
        "blink_time, blink_enabled FROM obs_settings"
    ))[0]

    assert tuple(general) == (1, "0.0.0.0", 54321, 1, 1)
    assert tuple(teamspeak) == ("10.0.0.5", 25639, "ts-api-key", 0)
    assert tuple(obs) == ("10.0.0.6", 4456, "obs-secret", 2, 7, 150, 1)


# --------------------------------------------------------------------------- #
# get_settings
# --------------------------------------------------------------------------- #

def test_get_settings_returns_none_if_a_table_is_empty(loop, database):
    # Only general_settings has a row; teamspeak and obs are empty.
    loop.run_until_complete(database.execute_and_commit(
        "INSERT INTO general_settings (id) VALUES (1)"
    ))
    # Make sure the insert really happened, so the test can't pass by accident
    # (get_settings also returns None when it fails).
    rows = loop.run_until_complete(database.fetch_all("SELECT COUNT(*) FROM general_settings"))
    assert rows[0][0] == 1

    assert loop.run_until_complete(database.get_settings()) is None


def test_get_settings_returns_row_with_lowest_id(loop, database):
    expected = make_settings()
    loop.run_until_complete(database.upsert_settings(expected))  # stored with id 1

    # Add a second row (id 2) to every table, with different values.
    for sql in (
            "INSERT INTO general_settings (id, autoconnect, host, port) "
            "VALUES (2, 0, 'other-host', 1)",
            "INSERT INTO teamspeak_settings (id, ip, port, api) "
            "VALUES (2, '1.1.1.1', 1, 'other-api')",
            "INSERT INTO obs_settings (id, ip, port, password) "
            "VALUES (2, '2.2.2.2', 2, 'other-password')",
    ):
        loop.run_until_complete(database.execute_and_commit(sql))

    actual = loop.run_until_complete(database.get_settings())

    assert actual is not None
    assert_settings_equal(actual, expected)


def test_column_defaults_are_applied(loop, database):
    """Inserting only the required columns must produce the schema defaults."""
    for sql in (
            "INSERT INTO general_settings (id) VALUES (1)",
            "INSERT INTO teamspeak_settings (id, ip, port, api) VALUES (1, 'ts', 1, 'api')",
            "INSERT INTO obs_settings (id, ip, port, password) VALUES (1, 'obs', 2, 'pw')",
    ):
        loop.run_until_complete(database.execute_and_commit(sql))

    actual = loop.run_until_complete(database.get_settings())

    assert actual is not None
    assert actual.autoconnect == 0
    assert actual.host == "127.0.0.1"
    assert actual.port == 12345
    assert actual.speak_start_animation_enabled == 0
    assert actual.speak_end_animation_enabled == 0
    assert actual.teamspeak.user_mute_behavior == 1
    assert actual.obs.low_blink_interval == 0
    assert actual.obs.high_blink_interval == 0
    assert actual.obs.blink_time == 0
    assert actual.obs.blink_enabled == 0


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #

def test_settings_persist_across_instances(loop, data_path, tmp_path):
    expected = make_settings()

    first = create_database(loop, data_path)
    assert_isolated(loop, first, tmp_path)
    loop.run_until_complete(first.upsert_settings(expected))
    loop.run_until_complete(close_database(first))

    second = create_database(loop, data_path)
    try:
        actual = loop.run_until_complete(second.get_settings())
        assert actual is not None
        assert_settings_equal(actual, expected)
    finally:
        loop.run_until_complete(close_database(second))
