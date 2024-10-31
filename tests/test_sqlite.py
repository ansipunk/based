import sqlite3

import pytest
import sqlalchemy as sa

import based


async def test_sqlite_foreign_keys(database_url: str, table: sa.Table):
    if not database_url.startswith("sqlite"):
        return

    async with based.Database(database_url) as database:
        async with database.session() as session:
            query = """
                CREATE TABLE actors(
                    name TEXT,
                    movie_id INTEGER,
                    FOREIGN KEY(movie_id) REFERENCES movies(id)
                );
            """
            await session.execute(query)

            query = """
                INSERT INTO actors(name, movie_id)
                VALUES ('Ryan Duckling', 0);
            """

            with pytest.raises(sqlite3.IntegrityError):
                await session.execute(query)
