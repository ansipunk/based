import random
import string
import typing
from contextlib import asynccontextmanager

from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql import ClauseElement

from based import errors


class Backend:
    """A general database connection backend.

    Must be implemented in database specific backends and cannot be used directly.
    """

    _force_rollback: bool
    _connected: bool = False
    _connected_before: bool = False

    def __init__(self, url: str, *, force_rollback: bool = False) -> None:
        """Details of this method should be implementation specific."""
        _ = url
        self._force_rollback = force_rollback

    async def _connect(self) -> None:
        """Details of this method should be implementation specific."""
        raise NotImplementedError

    async def _disconnect(self) -> None:
        """Details of this method should be implementation specific."""
        raise NotImplementedError

    @asynccontextmanager
    async def _session(self) -> typing.AsyncGenerator["Session", None]:
        """Details of this method should be implementation specific.

        Backends implementing this method should acquire a new connection from the
        connection pool and yield it here.

        Queries in that session must be executed in a transaction that will only be
        committed if the context manager exited successfully.
        """
        raise NotImplementedError
        yield

    @asynccontextmanager
    async def session(self) -> typing.AsyncGenerator["Session", None]:
        """Get a session from the connection pool.

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
        if not self._connected:
            raise errors.DatabaseNotConnectedError

        async with self._session() as session:
            yield session

    async def connect(self) -> None:
        """Connect to the database.

        Raises:
            errors.DatabaseAlreadyConnectedError:
                Raised on attempt to connect an already connected database.
            errors.DatabaseReopenProhibitedError:
                Raised on attempt to reopen a previously disconnected database.
        """
        if self._connected:
            raise errors.DatabaseAlreadyConnectedError

        if self._connected_before:
            raise errors.DatabaseReopenProhibitedError

        await self._connect()
        self._connected = True
        self._connected_before = True

    async def disconnect(self) -> None:
        """Disconnect from the database.

        Raises:
            errors.DatabaseNotConnectedError:
                Raised on attempt to disconnect from a database that was not connected.
        """
        if not self._connected:
            raise errors.DatabaseNotConnectedError

        await self._disconnect()
        self._connected = False


class Session:
    """A general session object for executing queries."""

    _conn: typing.Any
    _dialect: Dialect
    _transaction_stack: typing.List[str]

    def __init__(  # noqa: D107
        self,
        conn: typing.Any,  # noqa: ANN401
        dialect: Dialect,
    ) -> None:
        self._conn = conn
        self._dialect = dialect
        self._transaction_stack = []

    async def _execute(
        self,
        query: typing.Union[ClauseElement, str],
        params: typing.Optional[
            typing.Union[
                typing.Dict[str, typing.Any],
                typing.List[typing.Any],
            ]
        ] = None,
    ) -> typing.Any:  # noqa: ANN401
        """Execute the provided query and return a corresponding Cursor object.

        As DBAPI compliant database drivers have similar APIs, this function should be
        universal for the majority of the drivers.

        Args:
            query:
                Can either be a SQLAlchemy query or a string query, both positional and
                non positional like `SELECT * FROM ?;` or `SELECT * FROM :table;`.
            params:
                Can be both positional or non positional or be missing at all.

        Returns:
            cursor:
                A cursor returned by the database driver after executing the query.
        """
        return await self._conn.execute(query, params)

    def _compile_query(
        self,
        query: ClauseElement,
    ) -> typing.Tuple[
        str,
        typing.Optional[
            typing.Union[
                typing.Dict[str, typing.Any],
                typing.List[typing.Any],
            ]
        ],
    ]:
        compiled_query = query.compile(
            dialect=self._dialect,
            compile_kwargs={"literal_binds": True},
        )

        return str(compiled_query), compiled_query.params

    def _cast_row(
        self,
        cursor: typing.Any,  # noqa: ANN401
        row: typing.Any,  # noqa: ANN401
    ) -> typing.Dict[str, typing.Any]:
        """Cast a driver specific Row object to a more general mapping."""
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}

    async def execute(
        self,
        query: typing.Union[ClauseElement, str],
        params: typing.Optional[
            typing.Union[
                typing.Dict[str, typing.Any],
                typing.List[typing.Any],
            ]
        ] = None,
    ) -> None:
        """Execute the provided query.

        Args:
            query:
                Can either be a SQLAlchemy query or a string query, both positional and
                non positional like `SELECT * FROM ?;` or `SELECT * FROM :table;`.
            params:
                Can be both positional or non positional or be missing at all.
        """
        if isinstance(query, ClauseElement):
            query, params = self._compile_query(query)
        await self._execute(query, params)

    async def fetch_one(
        self,
        query: typing.Union[ClauseElement, str],
        params: typing.Optional[
            typing.Union[
                typing.Dict[str, typing.Any],
                typing.List[typing.Any],
            ]
        ] = None,
    ) -> typing.Optional[typing.Dict[str, typing.Any]]:
        """Execute the provided query.

        Args:
            query:
                Can either be a SQLAlchemy query or a string query, both positional and
                non positional like `SELECT * FROM ?;` or `SELECT * FROM :table;`.
            params:
                Can be both positional or non positional or be missing at all.

        Returns:
            row:
                Result of the executed query, either a row casted to a dictionary or
                None if the database returned nothing.
        """
        if isinstance(query, ClauseElement):
            query, params = self._compile_query(query)

        cursor = await self._execute(query, params)
        row = await cursor.fetchone()
        if not row:
            return None
        row = self._cast_row(cursor, row)
        await cursor.close()
        return row

    async def fetch_all(
        self,
        query: typing.Union[ClauseElement, str],
        params: typing.Optional[
            typing.Union[
                typing.Dict[str, typing.Any],
                typing.List[typing.Any],
            ]
        ] = None,
    ) -> typing.List[typing.Dict[str, typing.Any]]:
        """Execute the provided query.

        Args:
            query:
                Can either be a SQLAlchemy query or a string query, both positional and
                non positional like `SELECT * FROM ?;` or `SELECT * FROM :table;`.
            params:
                Can be both positional or non positional or be missing at all.

        Returns:
            rows:
                Result of the executed query, a list of rows casted to dictionaries.
        """
        if isinstance(query, ClauseElement):
            query, params = self._compile_query(query)

        cursor = await self._execute(query, params)
        rows = await cursor.fetchall()
        rows = [self._cast_row(cursor, row) for row in rows]
        await cursor.close()
        return rows

    async def create_transaction(self) -> None:
        """Create a transaction and add it to the transaction stack."""
        transaction_name = "".join(random.choices(string.ascii_lowercase, k=20))
        query = f"SAVEPOINT {transaction_name};"
        await self._execute(query)
        self._transaction_stack.append(transaction_name)

    async def commit_transaction(self) -> None:
        """Commit the last transaction in the transaction stack."""
        transaction_name = self._transaction_stack[-1]
        query = f"RELEASE SAVEPOINT {transaction_name};"
        await self._execute(query)
        self._transaction_stack.pop()

    async def cancel_transaction(self) -> None:
        """Rollback the last transaction in the transaction stack."""
        transaction_name = self._transaction_stack[-1]
        query = f"ROLLBACK TO SAVEPOINT {transaction_name};"
        await self._execute(query)
        self._transaction_stack.pop()

    @asynccontextmanager
    async def transaction(self) -> typing.AsyncGenerator[None, None]:
        """Open a transaction.

        Commits it to the database if it was successful and rollbacks otherwise.
        """
        await self.create_transaction()

        try:
            yield
        except Exception:
            await self.cancel_transaction()
            raise
        else:
            await self.commit_transaction()
