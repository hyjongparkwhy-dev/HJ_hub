from typing import Any


class FakeDb:
    """Reader stand-in keyed by the exact SQL constant each query module uses."""

    def __init__(self, responses: dict[str, list[dict[str, Any]]] | None = None):
        self.responses = responses or {}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def all(self, sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        self.calls.append((sql, params or {}))
        return [dict(row) for row in self.responses.get(sql, [])]

    def one(self, sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
        rows = self.all(sql, params)
        return rows[0] if rows else None

    def params_for(self, sql: str) -> list[dict[str, Any]]:
        return [params for called, params in self.calls if called == sql]
