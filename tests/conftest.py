import os
import tempfile

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
):
    if not database_url.startswith("sqlite"):
        if sqlalchemy_utils.database_exists(database_url):
            sqlalchemy_utils.drop_database(database_url)

        sqlalchemy_utils.create_database(database_url)

    engine = sqlalchemy.create_engine(database_url)
    metadata.create_all(engine)

    conn = engine.connect()
    queries = [
        table.insert().values(title="Blade Sprinter 2049", year=2017),
        table.insert().values(title="Farwent", year=1996),
    ]
    for query in queries:
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

    if database_url.startswith("postgresql"):
        getconn_mock = mocker.spy(database._backend._pool, "getconn")
        putconn_mock = mocker.spy(database._backend._pool, "putconn")

    await database.connect()

    try:
        yield database
    finally:
        await database.disconnect()

        if database_url.startswith("postgresql"):
            assert getconn_mock.call_count == putconn_mock.call_count


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
