import typing
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from sqlalchemy import URL, make_url
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.interfaces import Dialect

from based.backends import Backend, Session


class PostgreSQL(Backend):
    """A PostgreSQL backend for based.Database using psycopg and psycopg_pool."""

    _pool: AsyncConnectionPool
    _force_rollback: bool
    _force_rollback_connection: AsyncConnection
    _dialect: Dialect

    def __init__(  # noqa: D107
        self,
        url: typing.Optional[str] = None,
        *,
        host: typing.Optional[str] = None,
        port: typing.Optional[str] = None,
        username: typing.Optional[str] = None,
        password: typing.Optional[str] = None,
        database: typing.Optional[str] = None,
        force_rollback: bool = False,
    ) -> None:
        if url:
            self._url = make_url(url)
        else:
            self._url = URL.create(
                username=username,
                password=password,
                host=host,
                port=port,
                database=database,
                drivername="psycopg",
                query={},
            )

        conninfo = (
            f"user={self._url.username} "
            f"password={self._url.password} "
            f"host={self._url.host} "
            f"port={self._url.port} "
            f"dbname={self._url.database}"
        )
        self._pool = AsyncConnectionPool(conninfo, open=False)
        self._force_rollback = force_rollback
        self._dialect = postgresql.dialect()

    async def _connect(self) -> None:
        await self._pool.open()

        if self._force_rollback:
            self._force_rollback_connection = await self._pool.getconn()

    async def _disconnect(self) -> None:
        if self._force_rollback:
            await self._force_rollback_connection.rollback()
            await self._pool.putconn(self._force_rollback_connection)

        await self._pool.close()

    @asynccontextmanager
    async def _session(self) -> typing.AsyncGenerator["Session", None]:
        if self._force_rollback:
            connection = self._force_rollback_connection
        else:
            connection = await self._pool.getconn()

        session = Session(connection, self._dialect)

        if self._force_rollback:
            await session.create_transaction()

            try:
                yield session
            except Exception:
                await session.cancel_transaction()
                raise
            else:
                await session.commit_transaction()
        else:
            try:
                yield session
            except Exception:
                await connection.rollback()
                raise
            else:
                await connection.commit()
            finally:
                await self._pool.putconn(connection)
