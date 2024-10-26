from asyncio import Lock
from contextlib import asynccontextmanager
from types import TracebackType
from typing import AsyncGenerator, Optional, Type

from based.backends import Backend, Session


class Database:
    _backend: Backend
    _force_rollback: bool
    _lock: Optional[Lock] = None

    def __init__(
        self,
        url: str,
        *,
        force_rollback: bool = False,
        use_lock: bool = False,
    ) -> None:
        url_parts = url.split("://")
        if len(url_parts) != 2:
            raise ValueError("Invalid database URL")
        schema = url_parts[0]

        if force_rollback or (schema == "sqlite" and use_lock):
            self._lock = Lock()

        if schema == "sqlite":
            from based.backends.sqlite import SQLite
            sqlite_url = url_parts[1][1:]
            self._backend = SQLite(
                sqlite_url, force_rollback=force_rollback,
            )
        elif schema == "postgresql":
            from based.backends.postgresql import PostgreSQL
            self._backend = PostgreSQL(url, force_rollback=force_rollback)
        else:
            raise ValueError(f"Unknown database schema: {schema}")

    async def connect(self) -> None:
        await self._backend.connect()

    async def disconnect(self) -> None:
        await self._backend.disconnect()

    @asynccontextmanager
    async def _with_lock(self) -> AsyncGenerator[None, None]:
        if self._lock is not None:
            async with self._lock:
                yield
        else:
            yield

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[Session, None]:
        async with self._with_lock():
            async with self._backend.session() as session:
                yield session

    async def __aenter__(self) -> "Database":
        await self.connect()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        await self.disconnect()

        if exc_val is not None:
            raise exc_val
