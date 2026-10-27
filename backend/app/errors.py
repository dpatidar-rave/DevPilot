"""Application errors that routes translate into local HTTP responses."""


class DatabaseNotReady(Exception):
    """The local SQLite file exists but migrations have not been applied."""
