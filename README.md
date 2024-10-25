# Based

A based asynchronous database connection manager.

Based is designed to be used with SQLAlchemy Core requests. Currently, the only
supported databases are SQLite and PostgreSQL. It's fairly simple to add a new
backend, should you need one. Work in progress - any contributions - issues or
pull requests - are very welcome. API might change, as library is still at its
early experiment stage.

This library is inspired by [databases](https://github.com/encode/databases).

## Usage

```bash
pip install based[sqlite]
```

```python
import based

database = based.Database("sqlite:///database.sqlite")
await database.connect()

async with database.session() as session:
    query = Movies.select().where(Movies.c.year >= 2010)
    movies = await session.fetch_all(query)

    if movies:
        async with session.transaction():
            query = "DELETE FROM movies WHERE year >= :year;"
            params = {"year": 2010}
            await session.execute(query, params)

            async with session.transaction():
                for movie in movies:
                    query = "INSERT INTO movies (title, year) VALUES (?, ?);"
                    params = [movie["title"], movie["year"] - 1000]
                    await session.execute(query, params)

await database.disconnect()
```

## `force_rollback`

Databases can be initialized in `force_rollback=True` mode. When it's enabled,
everything will work as it usually does, but all the changes to the database
will be discarded upon disconneciton. It can be useful for testing purposes,
where you don't want to manually clean up made changes after each test.

To make it possible, `Backend` object will only operate with one single session
and each new requested session will actually be the same session.

```python
async with Database(
	"postgresql://user:pass@localhost/based",
	force_rollback=True,
) as database:
	async with database.session() as session:
		query = Movies.insert().values(title="Newboy", year=2004)
		await session.execute(query)

async with Database(
	"postgresql://user:pass@localhost/based",
	force_rollback=True,
) as database:
	async with database.session() as session:
		query = Movies.select().where(Movies.c.title == "Newboy")
		movie = await session.execute(query)
		assert movie is None
```

## Connection pools and parallel requests

Based supports connection pools for PostgreSQL databases thanks to psycopg_pool.
However, when running in `force_rollback` mode, it will only use a single
connection so it can be rolled back upon database disconnection. SQLite is
unaffected by `force_rollback` mode, as it doesn't have a connection pool either
way. This means that PostgreSQL backend in `force_rollback` mode and SQLite
backend in both modes are not guaranteed to work consistently when multiple
sessions are used in parallel. Adding a lock might solve this problem with
variable performance impact.

## Design choices

As you can see, database backends are split into two classes - `BasedBackend`
and `Session`. This design choice might be not very clear with SQLite, however,
it is handy with backends that support connection pools like PostgreSQL.

## Contributing

This library was designed to make adding new backends as simple as possible. You
need to implement `Backend` class and add its initialization to the `Database`
class. You only need to implement methods that raise `NotImplementedError` in
the base class, adding private helpers as needed.

## TODO

- [ ] CI/CD
  - [ ] Building and uploading packages to PyPi
  - [x] Testing with multiple Python versions
- [ ] Database URL parsing and building
- [ ] Add comments and docstrings
- [ ] Add lock for PostgreSQL in `force_rollback` mode and SQLite in both modes
- [ ] Refactor tests
- [x] PostgreSQL backend
- [x] Replace nested sessions with transaction stack
