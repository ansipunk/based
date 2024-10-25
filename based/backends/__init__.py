import random
import string
import typing
from contextlib import asynccontextmanager

from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql import ClauseElement

from based import errors


class Backend:
    _force_rollback: bool
    _connected: bool = False
    _connected_before: bool = False

    def __init__(self, url: str, *, force_rollback: bool = False) -> None:
        _ = url
        self._force_rollback = force_rollback

    async def _connect(self) -> None:
        raise NotImplementedError

    async def _disconnect(self) -> None:
        raise NotImplementedError

    @asynccontextmanager
    async def _session(self) -> typing.AsyncGenerator["Session", None]:
        raise NotImplementedError
        yield

    @asynccontextmanager
    async def session(self) -> typing.AsyncGenerator["Session", None]:
        if not self._connected:
            raise errors.DatabaseNotConnectedError

        async with self._session() as session:
            yield session

    async def connect(self) -> None:
        if self._connected:
            raise errors.DatabaseAlreadyConnectedError

        if self._connected_before:
            raise errors.DatabaseReopenProhibitedError

        await self._connect()
        self._connected = True
        self._connected_before = True

    async def disconnect(self) -> None:
        if not self._connected:
            raise errors.DatabaseNotConnectedError

        await self._disconnect()
        self._connected = False


class Session:
    _conn: typing.Any
    _dialect: Dialect
    _transaction_stack: typing.List[str]

    def __init__(
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
        parameters: typing.Optional[typing.Union[
            typing.Dict[str, typing.Any],
            typing.List[typing.Any],
        ]] = None,
    ) -> typing.Any:  # noqa: ANN401
        return await self._conn.execute(query, parameters)

    def _compile_query(
        self, query: ClauseElement,
    ) -> typing.Tuple[
            str,
            typing.Optional[typing.Union[
                typing.Dict[str, typing.Any],
                typing.List[typing.Any],
            ]],
        ]:
        compiled_query = query.compile(dialect=self._dialect)
        str_query = str(compiled_query)

        if not compiled_query.params:
            return str_query, None

        if compiled_query.positional:  # type: ignore
            params = [
                compiled_query.params[key]
                for key in compiled_query.positiontup  # type: ignore
            ]
        else:
            params = compiled_query.params

        return str_query, params

    def _cast_row(
        self, cursor: typing.Any, row: typing.Any,  # noqa: ANN401
    ) -> typing.Dict[str, typing.Any]:
        fields = [column[0] for column in cursor.description]
        return {key: value for key, value in zip(fields, row)}

    async def execute(
        self,
        query: typing.Union[ClauseElement, str],
        parameters: typing.Optional[typing.Union[
            typing.Dict[str, typing.Any],
            typing.List[typing.Any],
        ]] = None,
    ) -> None:
        if isinstance(query, ClauseElement):
            query, parameters = self._compile_query(query)
        await self._execute(query, parameters)

    async def fetch_one(
        self,
        query: typing.Union[ClauseElement, str],
        parameters: typing.Optional[typing.Union[
            typing.Dict[str, typing.Any],
            typing.List[typing.Any],
        ]] = None,
    ) -> typing.Optional[typing.Dict[str, typing.Any]]:
        if isinstance(query, ClauseElement):
            query, parameters = self._compile_query(query)
        cursor = await self._execute(query, parameters)
        row = await cursor.fetchone()
        if not row:
            return None
        return self._cast_row(cursor, row)

    async def fetch_all(
        self,
        query: typing.Union[ClauseElement, str],
        parameters: typing.Optional[typing.Union[
            typing.Dict[str, typing.Any],
            typing.List[typing.Any],
        ]] = None,
    ) -> typing.List[typing.Dict[str, typing.Any]]:
        if isinstance(query, ClauseElement):
            query, parameters = self._compile_query(query)
        cursor = await self._execute(query, parameters)
        rows = await cursor.fetchall()
        return [self._cast_row(cursor, row) for row in rows]

    async def create_transaction(self) -> None:
        transaction_name = "".join(random.choices(string.ascii_lowercase, k=20))  # noqa: S311
        query = f"SAVEPOINT {transaction_name};"
        await self._execute(query)
        self._transaction_stack.append(transaction_name)

    async def commit_transaction(self) -> None:
        transaction_name = self._transaction_stack[-1]
        query = f"RELEASE SAVEPOINT {transaction_name};"
        await self._execute(query)
        self._transaction_stack.pop()

    async def cancel_transaction(self) -> None:
        transaction_name = self._transaction_stack[-1]
        query = f"ROLLBACK TO SAVEPOINT {transaction_name};"
        await self._execute(query)
        self._transaction_stack.pop()

    @asynccontextmanager
    async def transaction(self) -> typing.AsyncGenerator[None, None]:
        await self.create_transaction()

        try:
            yield
        except Exception:
            await self.cancel_transaction()
            raise
        else:
            await self.commit_transaction()
