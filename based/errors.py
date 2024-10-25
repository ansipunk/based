class BasedError(Exception):
    """General exception class."""


class DatabaseNotConnectedError(BasedError):
    pass


class DatabaseAlreadyConnectedError(BasedError):
    pass


class DatabaseReopenProhibitedError(BasedError):
    pass
