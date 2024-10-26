import pytest

import based


def test_database_invalid_database_url():
    with pytest.raises(ValueError):
        based.Database(":memory:")


async def test_database_connect_already_connected_db(database: based.Database):
    with pytest.raises(based.errors.DatabaseAlreadyConnectedError):
        await database.connect()


async def test_database_connect_previously_connected_db(database_url: str):
    database = based.Database(database_url, force_rollback=True)

    await database.connect()
    await database.disconnect()

    with pytest.raises(based.errors.DatabaseReopenProhibitedError):
        await database.connect()


def test_database_with_invalid_schema():
    with pytest.raises(ValueError):
        based.Database("unsupported://localhost")


async def test_database_not_connected_get_session(database_url: str):
    database = based.Database(database_url)

    with pytest.raises(based.errors.DatabaseNotConnectedError):
        async with database.session():
            pass


async def test_database_disconnect_not_connected_database(database_url: str):
    database = based.Database(database_url)

    with pytest.raises(based.errors.DatabaseNotConnectedError):
        await database.disconnect()


async def test_database_context_manager_exception(database_url: str):
    database = based.Database(database_url)

    with pytest.raises(Exception):
        async with database:
            raise Exception

    with pytest.raises(based.errors.DatabaseNotConnectedError):
        await database.disconnect()
