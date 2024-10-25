import typing
from contextlib import asynccontextmanager

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.interfaces import Dialect

from based.backends import Backend, Session


class PostgreSQL(Backend):
    _pool: AsyncConnectionPool
    _force_rollback: bool
    _force_rollback_connection: AsyncConnection
    _dialect: Dialect

    def __init__(self, url: str, *, force_rollback: bool = False) -> None:
        self._pool = AsyncConnectionPool(url, open=False)
        self._force_rollback = force_rollback
        self._dialect = postgresql.dialect()  # type: ignore

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
