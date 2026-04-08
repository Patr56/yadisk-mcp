"""Security-focused tests for all audit fixes."""

import asyncio
import os
import uuid
import pytest
from unittest.mock import patch

from yadisk_mcp.server import (
    _sanitize_error,
    _validate_url,
    _check_upload_path,
    _evict_completed_jobs,
    _upload_jobs,
    delete,
    rename,
    upload_local_file,
    upload_local_file_background,
    upload_from_url,
    get_upload_status,
)


# ─── M1: lazy token ───────────────────────────────────────────────────────────

def test_no_global_token_variable():
    """server module must not expose a module-level TOKEN string."""
    import yadisk_mcp.server as srv
    assert not hasattr(srv, "TOKEN"), "Global TOKEN variable must be removed"


def test_get_async_client_raises_without_token():
    from yadisk_mcp.server import get_async_client
    with patch.dict(os.environ, {}, clear=True):
        # Remove the token from env entirely
        env = {k: v for k, v in os.environ.items() if k != "YANDEX_DISK_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(RuntimeError, match="YANDEX_DISK_TOKEN"):
                get_async_client()


def test_get_async_client_reads_token_lazily():
    """Token must be read from env at call time, not at import time."""
    from yadisk_mcp.server import get_async_client
    with patch.dict(os.environ, {"YANDEX_DISK_TOKEN": "lazy-token-123"}):
        client = get_async_client()
        assert client is not None


# ─── L3: full UUID job IDs ────────────────────────────────────────────────────

async def test_job_id_is_full_uuid(patched_client, tmp_path):
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    result = await upload_local_file_background(str(f), "/file.bin")
    job_id = result["job_id"]
    # Full UUID: 36 chars (8-4-4-4-12 with hyphens)
    assert len(job_id) == 36
    # Must parse as valid UUID
    uuid.UUID(job_id)


# ─── L2: rename new_name validation ──────────────────────────────────────────

async def test_rename_rejects_slash_in_new_name(patched_client):
    with pytest.raises(ValueError, match="path separators"):
        await rename("/Documents/file.txt", "../../etc/passwd")


async def test_rename_rejects_backslash_in_new_name(patched_client):
    with pytest.raises(ValueError, match="path separators"):
        await rename("/Documents/file.txt", "bad\\name.txt")


async def test_rename_accepts_valid_name(patched_client):
    result = await rename("/Documents/old.txt", "new.txt")
    assert result["renamed"]["to"] == "/Documents/new.txt"


# ─── H2: delete root guard ────────────────────────────────────────────────────

async def test_delete_root_permanently_raises(patched_client):
    with pytest.raises(ValueError, match="root path"):
        await delete("/", permanently=True)


async def test_delete_root_slash_permanently_raises(patched_client):
    """Trailing slashes must not bypass the guard."""
    with pytest.raises(ValueError, match="root path"):
        await delete("///", permanently=True)


async def test_delete_root_to_trash_is_allowed(patched_client):
    """Moving root to trash (permanently=False) must NOT raise."""
    result = await delete("/", permanently=False)
    assert result["permanently"] is False


async def test_delete_disk_root_permanently_raises(patched_client):
    with pytest.raises(ValueError, match="root path"):
        await delete("disk:", permanently=True)


async def test_delete_normal_file_permanently_ok(patched_client):
    result = await delete("/Documents/file.txt", permanently=True)
    assert result["permanently"] is True


# ─── M3: URL validation in upload_from_url ───────────────────────────────────

def test_validate_url_rejects_ftp():
    with pytest.raises(ValueError, match="http or https"):
        _validate_url("ftp://example.com/file.zip")


def test_validate_url_rejects_file_scheme():
    with pytest.raises(ValueError, match="http or https"):
        _validate_url("file:///etc/passwd")


def test_validate_url_rejects_localhost():
    with pytest.raises(ValueError, match="disallowed host"):
        _validate_url("http://localhost/secret")


def test_validate_url_rejects_127():
    with pytest.raises(ValueError, match="disallowed host"):
        _validate_url("https://127.0.0.1/secret")


def test_validate_url_rejects_link_local():
    with pytest.raises(ValueError, match="disallowed host"):
        _validate_url("http://169.254.169.254/latest/meta-data/")


def test_validate_url_accepts_https():
    _validate_url("https://example.com/file.zip")  # must not raise


def test_validate_url_accepts_http():
    _validate_url("http://cdn.example.org/data.bin")  # must not raise


async def test_upload_from_url_rejects_bad_scheme(patched_client):
    with pytest.raises(ValueError, match="http or https"):
        await upload_from_url("ftp://example.com/file.zip", "/Downloads/file.zip")


async def test_upload_from_url_rejects_localhost(patched_client):
    with pytest.raises(ValueError, match="disallowed host"):
        await upload_from_url("http://localhost/secret", "/Downloads/secret")


# ─── H1: upload allowlist ─────────────────────────────────────────────────────

def test_check_upload_path_no_allowlist_passes(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hi")
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("YADISK_MCP_UPLOAD_ALLOWED_DIRS", None)
        result = _check_upload_path(str(f))
    assert result == os.path.realpath(str(f))


def test_check_upload_path_allowed_dir_passes(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hi")
    with patch.dict(os.environ, {"YADISK_MCP_UPLOAD_ALLOWED_DIRS": str(tmp_path)}):
        result = _check_upload_path(str(f))
    assert result == os.path.realpath(str(f))


def test_check_upload_path_outside_allowlist_raises(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("hi")
    other_dir = "/tmp/other_allowed_dir"
    with patch.dict(os.environ, {"YADISK_MCP_UPLOAD_ALLOWED_DIRS": other_dir}):
        with pytest.raises(PermissionError, match="not allowed"):
            _check_upload_path(str(f))


def test_check_upload_path_resolves_symlinks(tmp_path):
    """Symlink pointing outside allowlist must be caught."""
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.txt"
    secret.write_text("secret")
    link = allowed / "link.txt"
    link.symlink_to(secret)

    with patch.dict(os.environ, {"YADISK_MCP_UPLOAD_ALLOWED_DIRS": str(allowed)}):
        with pytest.raises(PermissionError, match="not allowed"):
            _check_upload_path(str(link))


async def test_upload_local_file_blocked_by_allowlist(patched_client, tmp_path):
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    with patch.dict(os.environ, {"YADISK_MCP_UPLOAD_ALLOWED_DIRS": "/tmp/nonexistent_dir"}):
        with pytest.raises(PermissionError, match="not allowed"):
            await upload_local_file(str(f), "/remote.bin")


async def test_upload_background_blocked_by_allowlist(patched_client, tmp_path):
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")
    with patch.dict(os.environ, {"YADISK_MCP_UPLOAD_ALLOWED_DIRS": "/tmp/nonexistent_dir"}):
        with pytest.raises(PermissionError, match="not allowed"):
            await upload_local_file_background(str(f), "/remote.bin")


# ─── M2: error sanitization ───────────────────────────────────────────────────

def test_sanitize_error_redacts_token_in_message():
    class FakeError(Exception):
        pass
    e = FakeError("Request failed: token=SUPERSECRETTOKEN123456 status=401")
    result = _sanitize_error(e)
    assert "SUPERSECRETTOKEN123456" not in result
    assert "<redacted>" in result


def test_sanitize_error_redacts_bearer():
    class FakeError(Exception):
        pass
    e = FakeError("Authorization: Bearer abcdef1234567890xyz")
    result = _sanitize_error(e)
    assert "abcdef1234567890xyz" not in result


def test_sanitize_error_redacts_url_query():
    class FakeError(Exception):
        pass
    e = FakeError("GET https://example.com/api?token=secretvalue&foo=bar failed")
    result = _sanitize_error(e)
    assert "secretvalue" not in result
    assert "<redacted>" in result


def test_sanitize_error_preserves_safe_message():
    class FakeError(Exception):
        pass
    e = FakeError("File not found: /home/user/docs/report.pdf")
    result = _sanitize_error(e)
    assert "File not found" in result


async def test_background_upload_error_is_sanitized(patched_client, tmp_path):
    """Error stored in job dict must not contain raw token strings."""
    f = tmp_path / "file.bin"
    f.write_bytes(b"data")

    patched_client.upload.side_effect = Exception(
        "Upload failed: token=MY_SECRET_TOKEN_XYZ status=401"
    )

    result = await upload_local_file_background(str(f), "/remote.bin")
    job_id = result["job_id"]

    await asyncio.sleep(0.1)

    status = await get_upload_status(job_id)
    assert status["status"] == "error"
    assert "MY_SECRET_TOKEN_XYZ" not in status.get("error", "")


# ─── M4: job dict size cap ────────────────────────────────────────────────────

def test_evict_completed_jobs_removes_done_entries():
    _upload_jobs.clear()
    # Fill with done jobs up to the cap
    from yadisk_mcp.server import _MAX_COMPLETED_JOBS
    for i in range(_MAX_COMPLETED_JOBS):
        _upload_jobs[f"job-{i}"] = {"status": "done"}
    # Add one active job that must NOT be evicted
    _upload_jobs["active-job"] = {"status": "uploading"}

    _evict_completed_jobs()

    assert "active-job" in _upload_jobs
    # All done entries should be gone
    done_remaining = [k for k, v in _upload_jobs.items() if v["status"] == "done"]
    assert done_remaining == []

    _upload_jobs.clear()


def test_evict_completed_jobs_noop_below_threshold():
    _upload_jobs.clear()
    _upload_jobs["j1"] = {"status": "done"}
    _upload_jobs["j2"] = {"status": "uploading"}

    _evict_completed_jobs()  # should not evict — below threshold

    assert "j1" in _upload_jobs
    assert "j2" in _upload_jobs
    _upload_jobs.clear()
