"""Tests for read-only mode — env var, configure(), and CLI arg."""

import os
import pytest
from unittest.mock import patch

import yadisk_mcp.server as srv
from yadisk_mcp.server import (
    configure,
    create_folder,
    delete,
    copy,
    move,
    rename,
    upload_local_file,
    upload_local_file_background,
    upload_from_url,
    get_upload_status,
    list_upload_jobs,
    publish,
    unpublish,
    restore_from_trash,
    empty_trash,
    disk_info,
    list_files,
    list_recent_files,
    search_files,
    get_metadata,
    get_download_url,
    get_public_resource,
    list_trash,
)
from tests.conftest import fake_resource, async_iter


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _read_only_env():
    return patch.dict(os.environ, {"YADISK_MCP_READ_ONLY": "true"})


# ─── Priority: configure() overrides env var ─────────────────────────────────

async def test_configure_false_overrides_env_var(patched_client, tmp_path):
    """configure(read_only=False) must allow writes even when env var is set."""
    configure(read_only=False)
    try:
        with _read_only_env():
            result = await create_folder("/Test")
            assert result == {"created": "/Test"}
    finally:
        configure(read_only=None)  # reset


async def test_configure_true_enables_read_only_without_env(patched_client):
    """configure(read_only=True) must block writes even without env var."""
    configure(read_only=True)
    try:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("YADISK_MCP_READ_ONLY", None)
            with pytest.raises(PermissionError, match="read-only mode"):
                await create_folder("/Test")
    finally:
        configure(read_only=None)


async def test_configure_none_defers_to_env_var(patched_client):
    """configure(read_only=None) must fall back to env var."""
    configure(read_only=None)
    with _read_only_env():
        with pytest.raises(PermissionError, match="read-only mode"):
            await create_folder("/Test")


# ─── Env var activates read-only ─────────────────────────────────────────────

async def test_env_var_true_blocks_writes(patched_client):
    configure(read_only=None)
    with _read_only_env():
        with pytest.raises(PermissionError, match="read-only mode"):
            await empty_trash()


async def test_env_var_false_allows_writes(patched_client):
    configure(read_only=None)
    with patch.dict(os.environ, {"YADISK_MCP_READ_ONLY": "false"}):
        result = await empty_trash()
        assert result == {"trash": "emptied"}


# ─── All write tools are blocked ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_config():
    """Ensure _config is reset to None after each test."""
    yield
    configure(read_only=None)


@pytest.fixture
def read_only(patched_client):
    configure(read_only=True)
    yield patched_client


async def test_ro_create_folder(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await create_folder("/Folder")


async def test_ro_delete(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await delete("/file.txt")


async def test_ro_copy(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await copy("/src.txt", "/dst.txt")


async def test_ro_move(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await move("/src.txt", "/dst.txt")


async def test_ro_rename(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await rename("/file.txt", "new.txt")


async def test_ro_upload_local_file(read_only, tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"x")
    with pytest.raises(PermissionError, match="read-only mode"):
        await upload_local_file(str(f), "/f.bin")


async def test_ro_upload_local_file_background(read_only, tmp_path):
    f = tmp_path / "f.bin"
    f.write_bytes(b"x")
    with pytest.raises(PermissionError, match="read-only mode"):
        await upload_local_file_background(str(f), "/f.bin")


async def test_ro_upload_from_url(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await upload_from_url("https://example.com/f.zip", "/f.zip")


async def test_ro_get_upload_status(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await get_upload_status("some-job-id")


async def test_ro_list_upload_jobs(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await list_upload_jobs()


async def test_ro_publish(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await publish("/file.txt")


async def test_ro_unpublish(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await unpublish("/file.txt")


async def test_ro_restore_from_trash(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await restore_from_trash("/trash/file.txt")


async def test_ro_empty_trash(read_only):
    with pytest.raises(PermissionError, match="read-only mode"):
        await empty_trash()


# ─── Read tools are NOT blocked ───────────────────────────────────────────────

async def test_ro_disk_info_allowed(read_only):
    info = read_only
    info.get_disk_info.return_value.total_space = 10
    info.get_disk_info.return_value.used_space = 1
    info.get_disk_info.return_value.trash_size = 0
    info.get_disk_info.return_value.user = None
    result = await disk_info()
    assert "total_space" in result


async def test_ro_list_files_allowed(read_only):
    read_only.listdir = async_iter([])
    result = await list_files("/")
    assert result == []


async def test_ro_list_recent_files_allowed(read_only):
    read_only.get_last_uploaded = async_iter([])
    result = await list_recent_files()
    assert result == []


async def test_ro_search_files_allowed(read_only):
    read_only.search = async_iter([])
    result = await search_files("query")
    assert result == []


async def test_ro_get_metadata_allowed(read_only):
    read_only.get_meta.return_value = fake_resource(name="f.txt", path="/f.txt")
    result = await get_metadata("/f.txt")
    assert result["name"] == "f.txt"


async def test_ro_get_download_url_allowed(read_only):
    read_only.get_download_link.return_value = "https://dl.example.com/f"
    result = await get_download_url("/f.txt")
    assert "url" in result


async def test_ro_list_trash_allowed(read_only):
    read_only.trash_listdir = async_iter([])
    result = await list_trash()
    assert result == []


async def test_ro_get_public_resource_allowed(read_only):
    read_only.get_public_meta.return_value = fake_resource(name="pub.txt", path="/pub.txt")
    result = await get_public_resource("public-key-123")
    assert result["name"] == "pub.txt"


# ─── CLI: --read-only flag ────────────────────────────────────────────────────

def test_main_read_only_flag_sets_config():
    """--read-only CLI flag must call configure(read_only=True)."""
    configure(read_only=None)
    with patch("sys.argv", ["yadisk-mcp", "--read-only"]):
        with patch("yadisk_mcp.server.mcp.run"):  # don't actually start the server
            srv.main()
    assert srv._config["read_only"] is True
    configure(read_only=None)  # reset


def test_main_no_flag_does_not_set_config():
    """Without --read-only flag, configure() must not override env var."""
    configure(read_only=None)
    with patch("sys.argv", ["yadisk-mcp"]):
        with patch("yadisk_mcp.server.mcp.run"):
            srv.main()
    assert srv._config["read_only"] is None
