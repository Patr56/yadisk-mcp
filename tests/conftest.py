"""Shared fixtures for yadisk-mcp tests."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def async_iter(items):
    """Return a MagicMock that acts as a sync callable returning an AsyncIterableMock.
    Use for methods the server calls as `async for x in client.method(...):`
    """
    return MagicMock(return_value=AsyncIterableMock(items))


class AsyncIterableMock:
    """Async iterable for mocking `async for item in client.listdir(...):`"""

    def __init__(self, items):
        self._items = list(items)

    def __aiter__(self):
        self._iter = iter(self._items)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


def fake_resource(**kwargs):
    """Return a MagicMock with all attributes _resource_to_dict reads."""
    r = MagicMock()
    r.name = kwargs.get("name", "file.txt")
    r.path = kwargs.get("path", "/file.txt")
    r.type = kwargs.get("type", "file")
    r.size = kwargs.get("size", 1024)
    r.created = kwargs.get("created", "2026-01-01")
    r.modified = kwargs.get("modified", "2026-01-01")
    r.media_type = kwargs.get("media_type", None)
    r.mime_type = kwargs.get("mime_type", None)
    r.public_url = kwargs.get("public_url", None)
    r.public_key = kwargs.get("public_key", None)
    r.embedded = None
    return r


@pytest.fixture
def mock_client():
    client = AsyncMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.fixture
def patched_client(mock_client):
    with patch("yadisk_mcp.server.get_async_client", return_value=mock_client):
        yield mock_client
