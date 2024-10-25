import pytest

import based.backends


async def test_abstract_backend(database_url: str):
    backend = based.backends.Backend(database_url)

    with pytest.raises(NotImplementedError):
        await backend.connect()

    backend._connected = True

    with pytest.raises(NotImplementedError):
        async with backend.session():
            pass

    with pytest.raises(NotImplementedError):
        await backend.disconnect()
