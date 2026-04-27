from abc import ABC, abstractmethod


class DataStore(ABC):
    """Abstract interface all data backends must implement.

    To add a new database backend:
      1. Create db/<your_backend>.py and subclass DataStore.
      2. Add a branch in db/__init__.py:create_datastore().
      3. Set DB_TYPE=<your_backend> in .env.
    """

    @abstractmethod
    def get_summary(self) -> dict: ...

    @abstractmethod
    def get_charts(self) -> dict: ...

    @abstractmethod
    def get_table(self, limit: int, offset: int) -> list[dict]: ...

    @abstractmethod
    def search(self, keyword: str, limit: int) -> list[dict]: ...
