"""Tests for safe-delete mode.

In safe-delete mode nothing is ever destroyed:
- delete() moves the item to /LEGACY/<YYYY-MM-DD>/<original path> instead of removing it;
- permanent deletion, emptying Trash and any overwrite=True are refused;
- items already inside /LEGACY are left for the owner to clean up manually.
"""

import os
import pytest
from unittest.mock import AsyncMock, patch

import yadisk_mcp.server as srv
from yadisk_mcp.server import (
    configure,
    delete,
    empty_trash,
    copy,
    move,
    upload_local_file,
    upload_local_file_background,
    upload_from_url,
    restore_from_trash,
)


@pytest.fixture
def safe(patched_client):
    configure(safe_delete=True)
    patched_client.exists = AsyncMock(return_value=False)
    with patch.object(srv, "_today", return_value="2026-11-13"), \
         patch.object(srv, "_now_hms", return_value="101500"):
        yield patched_client
    configure(safe_delete=None)


def _existing(*paths):
    s = set(paths)
    return AsyncMock(side_effect=lambda p: p in s)


# ─── delete → move to /LEGACY ─────────────────────────────────────────────────

async def test_delete_moves_file_to_legacy(safe):
    safe.exists = _existing("/Docs")
    result = await delete("/Docs/a.txt")

    safe.remove.assert_not_called()
    safe.move.assert_awaited_once_with(
        "/Docs/a.txt", "/LEGACY/2026-11-13/Docs/a.txt", overwrite=False
    )
    assert result["moved_to"] == "/LEGACY/2026-11-13/Docs/a.txt"
    assert result["permanently"] is False


async def test_delete_creates_missing_legacy_parents(safe):
    await delete("/Docs/Sub/a.txt")
    created = [c.args[0] for c in safe.mkdir.await_args_list]
    assert created == [
        "/LEGACY",
        "/LEGACY/2026-11-13",
        "/LEGACY/2026-11-13/Docs",
        "/LEGACY/2026-11-13/Docs/Sub",
    ]


async def test_delete_skips_existing_legacy_parents(safe):
    safe.exists = _existing("/LEGACY", "/LEGACY/2026-11-13")
    await delete("/Docs/a.txt")
    created = [c.args[0] for c in safe.mkdir.await_args_list]
    assert created == ["/LEGACY/2026-11-13/Docs"]


async def test_delete_normalizes_disk_prefix(safe):
    await delete("disk:/Docs/a.txt")
    safe.move.assert_awaited_once_with(
        "/Docs/a.txt", "/LEGACY/2026-11-13/Docs/a.txt", overwrite=False
    )


async def test_delete_adds_suffix_when_legacy_target_exists(safe):
    safe.exists = _existing("/LEGACY/2026-11-13/Docs/a.txt")
    result = await delete("/Docs/a.txt")
    assert result["moved_to"] == "/LEGACY/2026-11-13/Docs/a.txt__101500"


async def test_delete_folder_moves_whole_folder(safe):
    await delete("/Old Project/")
    safe.move.assert_awaited_once_with(
        "/Old Project", "/LEGACY/2026-11-13/Old Project", overwrite=False
    )


# ─── refusals ────────────────────────────────────────────────────────────────

async def test_permanent_delete_refused(safe):
    with pytest.raises(PermissionError, match="safe-delete"):
        await delete("/Docs/a.txt", permanently=True)
    safe.remove.assert_not_called()
    safe.move.assert_not_called()


@pytest.mark.parametrize("path", ["/", "disk:/", ""])
async def test_delete_root_refused(safe, path):
    with pytest.raises(PermissionError):
        await delete(path)
    safe.move.assert_not_called()


@pytest.mark.parametrize("path", ["/LEGACY", "/LEGACY/2026-11-13/a.txt", "/legacy/x"])
async def test_delete_inside_legacy_refused(safe, path):
    with pytest.raises(PermissionError, match="LEGACY"):
        await delete(path)
    safe.move.assert_not_called()
    safe.remove.assert_not_called()


async def test_empty_trash_refused(safe):
    with pytest.raises(PermissionError, match="safe-delete"):
        await empty_trash()
    safe.remove_trash.assert_not_called()


async def test_copy_overwrite_refused(safe):
    with pytest.raises(PermissionError, match="safe-delete"):
        await copy("/a", "/b", overwrite=True)
    safe.copy.assert_not_called()


async def test_move_overwrite_refused(safe):
    with pytest.raises(PermissionError, match="safe-delete"):
        await move("/a", "/b", overwrite=True)
    safe.move.assert_not_called()


async def test_upload_overwrite_refused(safe, tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("x")
    with pytest.raises(PermissionError, match="safe-delete"):
        await upload_local_file(str(f), "/x.txt", overwrite=True)
    safe.upload.assert_not_called()


async def test_upload_background_overwrite_refused(safe, tmp_path):
    f = tmp_path / "x.txt"
    f.write_text("x")
    with pytest.raises(PermissionError, match="safe-delete"):
        await upload_local_file_background(str(f), "/x.txt", overwrite=True)


async def test_upload_from_url_overwrite_refused(safe):
    with pytest.raises(PermissionError, match="safe-delete"):
        await upload_from_url("https://example.com/f.pdf", "/f.pdf", overwrite=True)
    safe.upload_by_link.assert_not_called()


async def test_restore_overwrite_refused(safe):
    with pytest.raises(PermissionError, match="safe-delete"):
        await restore_from_trash("/trash/a", overwrite=True)
    safe.restore_trash.assert_not_called()


# ─── allowed operations still work ───────────────────────────────────────────

async def test_copy_without_overwrite_allowed(safe):
    await copy("/a", "/b")
    safe.copy.assert_awaited_once_with("/a", "/b", overwrite=False)


async def test_move_without_overwrite_allowed(safe):
    await move("/a", "/b")
    safe.move.assert_awaited_once_with("/a", "/b", overwrite=False)


# ─── activation ──────────────────────────────────────────────────────────────

async def test_env_var_enables_safe_delete(patched_client):
    configure(safe_delete=None)
    with patch.dict(os.environ, {"YADISK_MCP_SAFE_DELETE": "true"}):
        with pytest.raises(PermissionError, match="safe-delete"):
            await empty_trash()


async def test_disabled_by_default(patched_client):
    configure(safe_delete=None)
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("YADISK_MCP_SAFE_DELETE", None)
        await empty_trash()
    patched_client.remove_trash.assert_awaited_once_with("/")


async def test_configure_safe_delete_keeps_read_only(patched_client):
    """Setting one option must not reset the other."""
    configure(read_only=True)
    try:
        configure(safe_delete=True)
        with pytest.raises(PermissionError, match="read-only"):
            await delete("/a.txt")
    finally:
        configure(read_only=None, safe_delete=None)


def test_cli_flag_enables_safe_delete():
    with patch.object(srv.mcp, "run"), \
         patch("sys.argv", ["yadisk-mcp", "--safe-delete"]):
        srv.main()
    try:
        assert srv._is_safe_delete() is True
    finally:
        configure(read_only=None, safe_delete=None)
