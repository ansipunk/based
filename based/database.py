from asyncio import Lock
from contextlib import asynccontextmanager
from types import TracebackType
from typing import AsyncGenerator, Optional, Type

from based.backends import Backend, Session


class Database:
    """An asynchronous database connection manager."""

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
        """Create a connection manager.

        It will initialize the required backend depending on the provided database URL.
        Currently, PostgreSQL with psycopg and psycopg_pool and SQLite with aiosqlite
        are supported.

        Instead of calling connect and disconnect methods explicitly, you can use the
        Database object as an asynchronous context manager:

            async with based.Database(url) as database:
                async with database.session() as session:
                    await session.execute(query)

        Args:
            url:
                Database URL should be a URL defined by RFC 1738, containing the correct
                schema like `postgresql://user:password@host:port/database`.
            force_rollback:
                If this flag is set to True, then all the queries to the database will
                be made in one single transaction which will be rolled back when the
                database is disconnected. This mode is intended to be used in tests.
            use_lock:
                If this flag is set to True, each session, obtained from this object,
                will share an asynchronous lock preventing them to be used in parallel.
                This is forced in the force_rollback mode, where all the connections are
                actually just one connection with a transaction, which may lead to
                unexpected bugs.

        Raises:
            ValueError:
                Can be raised when an invalid database URL is provided or the database
                schema is not supported.
        """
        url_parts = url.split("://")
        if len(url_parts) != 2:
            raise ValueError("Invalid database URL")
        schema = url_parts[0]

        if use_lock and (force_rollback or schema == "sqlite"):
            self._lock = Lock()

        if schema == "sqlite":
            from based.backends.sqlite import SQLite

            sqlite_url = url_parts[1][1:]
            self._backend = SQLite(
                sqlite_url,
                force_rollback=force_rollback,
            )
        elif schema == "postgresql":
            from based.backends.postgresql import PostgreSQL

            self._backend = PostgreSQL(url, force_rollback=force_rollback)
        elif schema == "mysql":
            from based.backends.mysql import MySQL

            self._backend = MySQL(url, force_rollback=force_rollback)
        else:
            raise ValueError(f"Unknown database schema: {schema}")

    async def connect(self) -> None:
        """Connect to the database.

        A disconnected database cannot be reopened due to psycopg limitations, should
        you need to disconnect and then reconnect to a database, you should delete the
        old connection manager and create a new one.

        Raises:
            errors.DatabaseAlreadyConnectedError:
                Raised on attempt to connect an already connected database.
            errors.DatabaseReopenProhibitedError:
                Raised on attempt to reopen a previously disconnected database.
        """
        await self._backend.connect()

    async def disconnect(self) -> None:
        """Disconnect from the database.

        A disconnected database cannot be reopened due to psycopg limitations, should
        you need to disconnect and then reconnect to a database, you should delete the
        old connection manager and create a new one.

        Raises:
            errors.DatabaseNotConnectedError:
                Raised on attempt to disconnect from a database that was not connected.
        """
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
        """Get a live connection from the connection pool.

        If force_rollback mode is enabled, on each invocation of this function, it will
        return the same connection. For this reason, obtaining and using sessions will
        engage asyncio.Lock which will not be released until the session is released.

        Sessions created this way will all implicitly create a transaction that will
        only be committed if the context manager was successfully exited.

        Yields:
            session:
                A connected based.Session object from the database's connection pool.

        Raises:
            errors.DatabaseNotConnectedError:
                Raised on attempt to get a session from a not connected database.
        """
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
