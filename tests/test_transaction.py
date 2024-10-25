import typing

import pytest
import sqlalchemy

import based


async def test_database_transaction(
    session: based.Session,
    table: sqlalchemy.Table,
    gen_movie: typing.Callable[None, typing.Tuple[str, int]],
):
    title, year = gen_movie()

    async with session.transaction():
        query = table.insert().values(title=title, year=year)
        await session.execute(query)

    query = table.select().where(table.c.title == title)
    movie = await session.fetch_one(query)
    assert movie["title"] == title
    assert movie["year"] == year


async def test_database_failed_transaction(
    session: based.Session,
    table: sqlalchemy.Table,
    gen_movie: typing.Callable[None, typing.Tuple[str, int]],
):
    title, year = gen_movie()

    with pytest.raises(Exception):
        async with session.transaction():
            query = table.insert().values(title=title, year=year)
            await session.execute(query)
            raise Exception

    query = table.select().where(table.c.title == title)
    movie = await session.fetch_one(query)
    assert movie is None


async def test_database_nested_transaction(
    session: based.Session,
    table: sqlalchemy.Table,
    gen_movie: typing.Callable[None, typing.Tuple[str, int]],
):
    title_a, year_a = gen_movie()
    title_b, year_b = gen_movie()

    async with session.transaction():
        query = table.insert().values(title=title_a, year=year_a)
        await session.execute(query)

        async with session.transaction():
            query = table.insert().values(title=title_b, year=year_a)
            await session.execute(query)

    query = table.select().where(table.c.title.in_((title_a, title_b)))
    movies = await session.fetch_all(query)
    assert len(movies) == 2


async def test_database_failed_nested_transaction(
    session: based.Session,
    table: sqlalchemy.Table,
    gen_movie: typing.Callable[None, typing.Tuple[str, int]],
):
    title_a, year_a = gen_movie()
    title_b, year_b = gen_movie()

    async with session.transaction():
        query = table.insert().values(title=title_a, year=year_a)
        await session.execute(query)

        with pytest.raises(Exception):
            async with session.transaction():
                query = table.insert().values(title=title_b, year=year_b)
                await session.execute(query)
                raise Exception

    query = table.select().where(table.c.title.in_((title_a, title_b)))
    movies = await session.fetch_all(query)
    assert len(movies) == 1
    assert movies[0]["title"] == title_a
