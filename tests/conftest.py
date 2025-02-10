import os
import random
import tempfile
import typing

import pytest
import pytest_mock
import sqlalchemy
import sqlalchemy_utils

import based

RAW_DATABASE_URLS = os.environ.get("BASED_TEST_DB_URLS", "")
DATABASE_URLS = RAW_DATABASE_URLS.split(",") if RAW_DATABASE_URLS else []
DATABASE_URLS = [database_url.strip() for database_url in DATABASE_URLS]
DATABASE_URLS = [*DATABASE_URLS, "sqlite"]


@pytest.fixture(scope="session")
def default_movie_a():
    return "Blade Sprinter 1949", 2017


@pytest.fixture(scope="session")
def default_movie_b():
    return "Farwent", 1996


@pytest.fixture
def gen_movie():
    movies = [
        ("Neten", 2020),
        ("Jojo Hare", 2017),
        ("North Park", 1997),
        ("Plastic Man", 2008),
        ("Dull Blinders", 2013),
        ("BoJohn Manhorse", 2014),
        ("Mulholland Walk", 2001),
        ("A Small Lebowski", 1998),
        ("Better Call Police", 2015),
        ("Glorious Gentlemen", 2009),
        ("It's never sunny in Wales", 2005),
        ("Bravery and Love in Las Vegas", 1998),
        ("Three Display Boards Inside Springfield, Missouri", 2017),
    ]

    def generate() -> str:
        return movies.pop(
            random.randrange(len(movies)),
        )

    return generate


@pytest.fixture(scope="session")
def metadata():
    return sqlalchemy.MetaData()


@pytest.fixture(scope="session")
def table(metadata: sqlalchemy.MetaData):
    return sqlalchemy.Table(
        "movies",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("title", sqlalchemy.Text, nullable=False),
        sqlalchemy.Column("year", sqlalchemy.Integer, nullable=False),
    )


@pytest.fixture(autouse=True, scope="session")
def _context(
    metadata: sqlalchemy.MetaData,
    table: sqlalchemy.Table,
    database_url: str,
    worker_id: str,
    default_movie_a: typing.Tuple[str, int],
    default_movie_b: typing.Tuple[str, int],
):
    if not database_url.startswith("sqlite"):
        if sqlalchemy_utils.database_exists(database_url):
            sqlalchemy_utils.drop_database(database_url)

        sqlalchemy_utils.create_database(database_url)

    engine = sqlalchemy.create_engine(database_url)
    metadata.create_all(engine)

    conn = engine.connect()
    for title, year in (default_movie_a, default_movie_b):
        query = table.insert().values(title=title, year=year)
        conn.execute(query)
    conn.commit()
    conn.close()

    engine.dispose()

    yield

    engine = sqlalchemy.create_engine(database_url)
    metadata.drop_all(engine)
    engine.dispose()

    if not database_url.startswith("sqlite"):
        sqlalchemy_utils.drop_database(database_url)


@pytest.fixture
async def database(database_url: str, mocker: pytest_mock.MockerFixture):
    database = based.Database(database_url, force_rollback=True)
    await database.connect()

    if database_url.startswith("postgresql"):
        getconn_mock = mocker.spy(database._backend._pool, "getconn")
        putconn_mock = mocker.spy(database._backend._pool, "putconn")
    elif database_url.startswith("mysql"):
        getconn_mock = mocker.spy(database._backend._pool, "acquire")
        putconn_mock = mocker.spy(database._backend._pool, "release")

    try:
        yield database
    finally:
        await database.disconnect()

        if database_url.startswith(("postgresql", "mysql")):
            # 1 is subtracted because one connection is always automatically
            # acquired when force rollback mode is engaged.
            assert getconn_mock.call_count == putconn_mock.call_count - 1


@pytest.fixture
async def session(database: based.Database):
    async with database.session() as session:
        yield session


@pytest.fixture(scope="session")
def database_url(raw_database_url: str, worker_id: str):
    if raw_database_url != "sqlite":
        dbinfo = raw_database_url.rsplit("/", maxsplit=1)
        dbinfo[1] = f"based-test-{worker_id}"
        yield "/".join(dbinfo)
    else:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = f"{tmpdir}/{worker_id}.sqlite"
            yield f"sqlite:///{db_path!s}"


def pytest_generate_tests(metafunc: pytest.Metafunc):
    if "raw_database_url" in metafunc.fixturenames:
        metafunc.parametrize("raw_database_url", DATABASE_URLS, scope="session")
