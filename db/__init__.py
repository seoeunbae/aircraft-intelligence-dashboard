from .base import DataStore
from config import Settings


def create_datastore(settings: Settings) -> DataStore:
    """Factory — returns the DataStore implementation for the configured backend.

    To add a new backend:
      1. Create db/<name>.py with a DataStore subclass.
      2. Add a branch below.
      3. Set DB_TYPE=<name> in .env.
    """
    if settings.db_type == "bigquery":
        from .bigquery import BigQueryDataStore
        return BigQueryDataStore(settings)

    raise ValueError(
        f"Unsupported DB_TYPE={settings.db_type!r}. "
        "Add a new DataStore subclass in db/ and register it here."
    )


__all__ = ["DataStore", "create_datastore"]
