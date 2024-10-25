import typing

import pytest
import sqlalchemy

import based


@pytest.mark.parametrize("force_rollback", [(True), (False)])
async def test_database_unsuccessful_session(
    database_url: str,
    table: sqlalchemy.Table,
    force_rollback: bool,
    gen_movie: typing.Callable[None, typing.Tuple[str, int]],
):
    title, year = gen_movie()

    async with based.Database(database_url, force_rollback=force_rollback) as database:
        with pytest.raises(Exception):
            async with database.session() as session:
                query = table.insert().values(title=title, year=year)
                await session.execute(query)
                raise Exception

        async with database.session() as session:
            query = table.select().where(table.c.title == title)
            movie = await session.fetch_one(query)
            assert movie is None


@pytest.mark.parametrize("force_rollback", [(True), (False)])
async def test_database_successful_session(
    database_url: str,
    table: sqlalchemy.Table,
    force_rollback: bool,
    gen_movie: typing.Callable[None, typing.Tuple[str, int]],
):
    title, year = gen_movie()

    async with based.Database(database_url, force_rollback=force_rollback) as database:
        async with database.session() as session:
            query = table.insert().values(title=title, year=year)
            await session.execute(query)

        async with database.session() as session:
            query = table.select().where(table.c.title == title)
            movie = await session.fetch_one(query)
            assert movie["title"] == title
            assert movie["year"] == year

        async with database.session() as session:
            query = table.delete().where(table.c.title == title)
            await session.execute(query)
