# Contributing to yadisk-mcp

## Quick start

```bash
git clone https://github.com/Patr56/yadisk-mcp
cd yadisk-mcp
pip install -e ".[dev]"
pytest
```

No `YANDEX_DISK_TOKEN` needed — all tests use mocks, no real API calls are made.

## Project structure

```
yadisk_mcp/server.py   — all 22 MCP tools in one file
tests/
  conftest.py          — shared fixtures: mock_client, patched_client, fake_resource
  test_disk_info.py
  test_listing.py      — list_files, list_recent_files, search_files
  test_metadata.py     — get_metadata
  test_crud.py         — create_folder, delete, copy, move, rename
  test_upload.py       — upload tools + background jobs
  test_sharing.py      — publish, unpublish, get_public_resource
  test_trash.py        — list_trash, restore_from_trash, empty_trash
```

## How tests work

Every tool follows the same pattern: `async with get_async_client() as client: ...`.
Tests patch `yadisk_mcp.server.get_async_client` with a mock and control what it returns.

```python
# Example
async def test_something(patched_client):
    patched_client.some_method.return_value = fake_resource(name="file.txt")
    result = await some_tool("/path")
    assert result["name"] == "file.txt"
```

For tools that iterate (`list_files`, `list_trash`, etc.) use `AsyncIterableMock`:

```python
from tests.conftest import AsyncIterableMock, fake_resource

patched_client.listdir.return_value = AsyncIterableMock([
    fake_resource(name="a.txt"),
    fake_resource(name="b.jpg"),
])
```

## Adding a new tool

1. Add `@mcp.tool()` function in `yadisk_mcp/server.py`
2. Add at least one test in the relevant `tests/test_*.py` file
3. **No real API calls in tests** — always mock the client
4. Run `pytest` before opening a PR

## PR checklist

- [ ] `pytest` passes locally
- [ ] New tool has a docstring with `Args:` section
- [ ] New tool has at least one test
- [ ] No new runtime dependencies without prior discussion in an issue
