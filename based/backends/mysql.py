import typing
from contextlib import asynccontextmanager

import asyncmy
from sqlalchemy import URL, make_url
from sqlalchemy.dialects.mysql.asyncmy import dialect
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql import ClauseElement

from based.backends import Backend, Session


class MySQL(Backend):
    """A MySQL backend for based.Database using asyncmy."""

    _url: URL
    _pool: asyncmy.Pool
    _force_rollback: bool
    _force_rollback_connection: asyncmy.Connection
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
                drivername="asyncmy",
                query={},
            )

        self._force_rollback = force_rollback
        self._dialect = dialect()

    async def _connect(self) -> None:
        self._pool = await asyncmy.create_pool(
            user=self._url.username,
            password=self._url.password,
            host=self._url.host,
            port=self._url.port,
            database=self._url.database,
        )

        if self._force_rollback:
            self._force_rollback_connection = await self._pool.acquire()

    async def _disconnect(self) -> None:
        if self._force_rollback:
            await self._force_rollback_connection.rollback()
            self._pool.release(self._force_rollback_connection)

        self._pool.close()
        await self._pool.wait_closed()

    @asynccontextmanager
    async def _session(self) -> typing.AsyncGenerator["Session", None]:
        if self._force_rollback:
            connection = self._force_rollback_connection
        else:
            connection = await self._pool.acquire()

        session = _MySQLSession(connection, self._dialect)

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
                self._pool.release(connection)


class _MySQLSession(Session):
    async def _execute(
        self,
        query: typing.Union[ClauseElement, str],
        params: typing.Optional[
            typing.Union[
                typing.Dict[str, typing.Any],
                typing.List[typing.Any],
            ]
        ] = None,
    ) -> asyncmy.cursors.Cursor:
        cursor = self._conn.cursor()
        await cursor.execute(query, params)
        return cursor
