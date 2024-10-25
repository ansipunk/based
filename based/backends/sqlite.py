import typing
from contextlib import asynccontextmanager

from aiosqlite import Connection, connect
from sqlalchemy.dialects import sqlite
from sqlalchemy.engine.interfaces import Dialect

from based.backends import Backend, Session


class SQLite(Backend):
    _conn: Connection
    _force_rollback: bool
    _force_rollback_session: "Session"
    _dialect: Dialect

    def __init__(self, url: str, *, force_rollback: bool = False) -> None:
        self._conn = connect(url, isolation_level=None)
        self._force_rollback = force_rollback
        self._dialect = sqlite.dialect()  # type: ignore

    async def _connect(self) -> None:
        await self._conn

        if self._force_rollback:
            session = Session(self._conn, self._dialect)
            await session.create_transaction()
            self._force_rollback_session = session

    async def _disconnect(self) -> None:
        if self._force_rollback:
            await self._force_rollback_session.cancel_transaction()

        await self._conn.close()

    @asynccontextmanager
    async def _session(self) -> typing.AsyncGenerator["Session", None]:
        if self._force_rollback:
            session = self._force_rollback_session
        else:
            session = Session(self._conn, self._dialect)

        await session.create_transaction()

        try:
            yield session
        except Exception:
            await session.cancel_transaction()
            raise
        else:
            await session.commit_transaction()
