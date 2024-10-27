class BasedError(Exception):
    """General exception class."""


class DatabaseNotConnectedError(BasedError):
    """Raised on attempt to use a database that was not connected."""


class DatabaseAlreadyConnectedError(BasedError):
    """Raised on attempt to connect to an already connected database."""


class DatabaseReopenProhibitedError(BasedError):
    """Raised on attempt to reconnect to a previously disconnected database."""
