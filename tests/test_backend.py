import contextlib
import typing

import pytest
import sqlalchemy

import based


async def test_database_force_rollback(
    table: sqlalchemy.Table,
    database_url: str,
    gen_movie: typing.Callable[[], typing.Tuple[str, int]],
):
    title, year = gen_movie()

    async with based.Database(database_url, force_rollback=True) as database:
        async with database.session() as session:
            query = table.insert().values(title=title, year=year)
            await session.execute(query)

    async with based.Database(database_url, force_rollback=True) as database:
        async with database.session() as session:
            query = table.select().where(table.c.title == title)
            movie = await session.fetch_one(query)
            assert movie is None


async def test_database_force_rollback_with_lock(
    table: sqlalchemy.Table,
    database_url: str,
    gen_movie: typing.Callable[[], typing.Tuple[str, int]],
):
    title, year = gen_movie()

    async with based.Database(
        database_url,
        force_rollback=True,
        use_lock=True,
    ) as database:
        async with database.session() as session:
            query = table.insert().values(title=title, year=year)
            await session.execute(query)

    async with based.Database(database_url, force_rollback=True) as database:
        async with database.session() as session:
            query = table.select().where(table.c.title == title)
            movie = await session.fetch_one(query)
            assert movie is None


async def test_database_no_force_rollback(
    table: sqlalchemy.Table,
    database_url: str,
    gen_movie: typing.Callable[[], typing.Tuple[str, int]],
):
    title, year = gen_movie()

    async with based.Database(database_url, force_rollback=False) as database:
        async with database.session() as session:
            query = table.insert().values(title=title, year=year)
            await session.execute(query)

    async with based.Database(database_url, force_rollback=False) as database:
        async with database.session() as session:
            query = table.select().where(table.c.title == title)
            movie = await session.fetch_one(query)
            assert movie["title"] == title
            assert movie["year"] == year

    async with based.Database(database_url, force_rollback=False) as database:
        async with database.session() as session:
            query = table.delete().where(table.c.title == title)
            await session.execute(query)


async def test_abstract_backend(database_url: str):
    backend = based.backends.Backend(database_url)

    with pytest.raises(NotImplementedError):
        await backend.connect()

    backend._connected = True

    with pytest.raises(NotImplementedError):
        async with backend.session():
            pass

    with pytest.raises(NotImplementedError):
        await backend.disconnect()


async def test_disconnect_with_failed_transaction_force_rollback(database_url: str):
    async with based.Database(database_url, force_rollback=True) as database:
        async with database.session() as session:
            with contextlib.suppress(Exception):
                await session.execute("SELECT 1 FROM nonexistent;")


async def test_disconnect_with_failed_transaction_no_force_rollback(database_url: str):
    async with based.Database(database_url, force_rollback=False) as database:
        async with database.session() as session:
            with contextlib.suppress(Exception):
                await session.execute("SELECT 1 FROM nonexistent;")
