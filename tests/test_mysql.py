import sqlalchemy as sa

import based


async def test_mysql_url_building(database_url: str):
    if not database_url.startswith("mysql"):
        return

    url = sa.make_url(database_url)

    async with based.Database(
        username=url.username,
        password=url.password,
        host=url.host,
        port=url.port,
        database=url.database,
        schema="mysql",
    ) as database:
        async with database.session() as session:
            await session.execute("SELECT 1;")
