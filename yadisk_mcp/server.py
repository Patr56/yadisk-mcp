"""Yandex Disk MCP Server."""

import os
import re
import uuid
import asyncio
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
import yadisk
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("yadisk")

# ─── Background upload jobs ───────────────────────────────────────────────────
_upload_jobs: dict[str, dict] = {}
_MAX_COMPLETED_JOBS = 200  # cap to prevent unbounded memory growth


# ─── Configuration ────────────────────────────────────────────────────────────

# None = not explicitly set (fall back to env var); True/False = explicit override
_config: dict[str, bool | None] = {"read_only": None, "safe_delete": None}

_UNSET: Any = object()

# Safe-delete mode moves "deleted" items here instead of removing them.
LEGACY_ROOT = "/LEGACY"

_TRUTHY = ("1", "true", "yes")


def configure(*, read_only: bool | None = _UNSET, safe_delete: bool | None = _UNSET) -> None:
    """Configure the MCP server programmatically.

    Explicit values set here take priority over environment variables.
    Options that are not passed keep their current value.

    Args:
        read_only: If True, all write operations are disabled. If False, explicitly
                   enables writes even when YADISK_MCP_READ_ONLY env var is set.
                   If None, defers to the YADISK_MCP_READ_ONLY env var.
        safe_delete: If True, nothing is ever destroyed: delete() moves items to
                     /LEGACY/<date>/..., permanent deletion, emptying Trash and
                     overwrite=True are refused. If None, defers to the
                     YADISK_MCP_SAFE_DELETE env var.
    """
    if read_only is not _UNSET:
        _config["read_only"] = read_only
    if safe_delete is not _UNSET:
        _config["safe_delete"] = safe_delete


# ─── Security helpers ─────────────────────────────────────────────────────────

def get_async_client() -> yadisk.AsyncClient:
    # M1: read token lazily — picks up rotations, avoids global string in memory
    token = os.environ.get("YANDEX_DISK_TOKEN", "")
    if not token:
        raise RuntimeError(
            "YANDEX_DISK_TOKEN environment variable is not set. "
            "Get a token at https://oauth.yandex.ru and set it."
        )
    return yadisk.AsyncClient(token=token)


def _assert_writable() -> None:
    """Raise PermissionError if the server is running in read-only mode.

    Priority: configure(read_only=...) > --read-only CLI flag > YADISK_MCP_READ_ONLY env var.
    """
    explicit = _config["read_only"]
    if explicit is not None:
        read_only = explicit
    else:
        read_only = os.environ.get("YADISK_MCP_READ_ONLY", "").lower() in ("1", "true", "yes")
    if read_only:
        raise PermissionError(
            "The server is running in read-only mode. This operation is not allowed."
        )


def _is_safe_delete() -> bool:
    """Priority: configure(safe_delete=...) > --safe-delete CLI flag > YADISK_MCP_SAFE_DELETE."""
    explicit = _config["safe_delete"]
    if explicit is not None:
        return explicit
    return os.environ.get("YADISK_MCP_SAFE_DELETE", "").lower() in _TRUTHY


def _refuse_in_safe_delete(what: str) -> None:
    if _is_safe_delete():
        raise PermissionError(
            f"{what} is not allowed: the server is running in safe-delete mode. "
            f"Use delete() to move items to {LEGACY_ROOT} instead."
        )


def _assert_no_overwrite(overwrite: bool) -> None:
    if overwrite:
        _refuse_in_safe_delete("Overwriting existing items (overwrite=True)")


def _normalize_path(path: str) -> str:
    """'disk:/a/b/' -> '/a/b'; '' or 'disk:' -> '/'."""
    p = path.strip()
    if p.startswith("disk:"):
        p = p[len("disk:"):]
    p = "/" + p.strip("/")
    return p


def _is_inside_legacy(normalized: str) -> bool:
    root = LEGACY_ROOT.casefold()
    p = normalized.casefold()
    return p == root or p.startswith(root + "/")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _now_hms() -> str:
    return datetime.now().strftime("%H%M%S")


async def _ensure_dir(client: Any, path: str) -> None:
    """Create `path` and any missing parents (Yandex mkdir is not recursive)."""
    current = ""
    for part in path.strip("/").split("/"):
        current = f"{current}/{part}"
        if await client.exists(current):
            continue
        try:
            await client.mkdir(current)
        except yadisk.exceptions.PathExistsError:
            pass


async def _legacy_target(client: Any, normalized: str) -> str:
    target = f"{LEGACY_ROOT}/{_today()}{normalized}"
    if await client.exists(target):
        target = f"{target}__{_now_hms()}"
    return target


def _get_upload_allowed_dirs() -> list[str] | None:
    """Return resolved allowed dirs from YADISK_MCP_UPLOAD_ALLOWED_DIRS, or None if unset."""
    raw = os.environ.get("YADISK_MCP_UPLOAD_ALLOWED_DIRS", "")
    if not raw:
        return None
    dirs = [os.path.realpath(d.strip()) for d in raw.split(",") if d.strip()]
    return dirs or None


def _check_upload_path(local_path: str) -> str:
    """Resolve symlinks/.. and enforce allowlist. Returns the resolved path."""
    real = os.path.realpath(local_path)
    allowed = _get_upload_allowed_dirs()
    if allowed is not None:
        if not any(real == d or real.startswith(d + os.sep) for d in allowed):
            raise PermissionError(
                f"Upload from '{real}' is not allowed. "
                f"Allowed directories: {', '.join(allowed)}. "
                "Set YADISK_MCP_UPLOAD_ALLOWED_DIRS to configure."
            )
    return real


def _validate_url(url: str) -> None:
    """Reject non-http(s) schemes and localhost/link-local hosts (SSRF mitigation)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(
            f"URL must use http or https scheme, got: {parsed.scheme!r}"
        )
    host = (parsed.hostname or "").lower()
    blocked = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
    if host in blocked or host.startswith("169.254."):
        raise ValueError(f"URL points to a disallowed host: {host!r}")


def _sanitize_error(e: Exception) -> str:
    """Return error message with OAuth tokens and credential strings redacted."""
    msg = str(e)
    # Redact token= / bearer <value> patterns
    msg = re.sub(
        r'(?i)(token|bearer|access_token)[=:\s]+[A-Za-z0-9_\-\.]{8,}',
        r'\1=<redacted>',
        msg,
    )
    # Redact URL query strings that might carry tokens
    msg = re.sub(r'\?[^\s]*', '?<redacted>', msg)
    return msg


def _evict_completed_jobs() -> None:
    """Drop finished jobs when the dict exceeds _MAX_COMPLETED_JOBS."""
    if len(_upload_jobs) < _MAX_COMPLETED_JOBS:
        return
    done_keys = [
        k for k, v in _upload_jobs.items()
        if v.get("status") in ("done", "error")
    ]
    for k in done_keys:
        del _upload_jobs[k]


class _ProgressFile:
    """Wraps an async file and tracks bytes read for progress reporting."""

    def __init__(self, f: Any, job: dict) -> None:
        self._f = f
        self._job = job

    async def read(self, size: int = -1) -> bytes:
        data = await self._f.read(size)
        self._job["bytes_uploaded"] = self._job.get("bytes_uploaded", 0) + len(data)
        total = self._job.get("size", 0)
        if total:
            self._job["progress"] = round(self._job["bytes_uploaded"] / total * 100, 1)
        return data

    async def tell(self) -> int:
        return await self._f.tell()

    async def seek(self, *args: Any) -> int:
        return await self._f.seek(*args)

    async def close(self) -> None:
        await self._f.close()


# ─── Disk info ───────────────────────────────────────────────────────────────

@mcp.tool()
async def disk_info() -> dict:
    """Get Yandex Disk quota and usage information."""
    async with get_async_client() as client:
        info = await client.get_disk_info()
        return {
            "total_space": info.total_space,
            "used_space": info.used_space,
            "trash_size": info.trash_size,
            "free_space": info.total_space - info.used_space,
            "user": {
                "login": info.user.login if info.user else None,
                "display_name": info.user.display_name if info.user else None,
            },
        }


# ─── Directory listing ────────────────────────────────────────────────────────

@mcp.tool()
async def list_files(
    path: str = "/",
    limit: int = 50,
    offset: int = 0,
    sort: str = "name",
) -> list[dict]:
    """List files and folders at the given Yandex Disk path.

    Args:
        path: Path on Yandex Disk (e.g. "/" or "/Documents").
        limit: Max items to return (1–100).
        offset: Offset for pagination.
        sort: Sort field: name, created, modified, size. Prefix with "-" for descending.
    """
    async with get_async_client() as client:
        result = []
        async for item in client.listdir(
            path,
            limit=min(limit, 100),
            offset=offset,
            sort=sort,
        ):
            result.append(_resource_to_dict(item))
        return result


@mcp.tool()
async def list_recent_files(limit: int = 20) -> list[dict]:
    """List recently uploaded files across the entire disk.

    Args:
        limit: Max number of files to return (1–100).
    """
    async with get_async_client() as client:
        # get_last_uploaded is a coroutine returning a list (not an async generator)
        items = await client.get_last_uploaded(limit=min(limit, 100))
        return [_resource_to_dict(item) for item in items]


@mcp.tool()
async def search_files(query: str, limit: int = 20, media_type: str | None = None) -> list[dict]:
    """Search for files on Yandex Disk by name (case-insensitive substring).

    The Yandex Disk API has no search endpoint, so this scans the flat list of
    all files on the disk and filters by name. Folders are not matched. On a
    large disk this can take a while; use media_type to narrow the scan.

    Args:
        query: Substring to look for in file names.
        limit: Max results (1–100).
        media_type: Optional media type filter: audio, backup, book, compressed,
                    data, development, disk_image, document, encoded, executable,
                    flash, font, image, msi, text, unknown, video, web.
    """
    needle = query.strip().casefold()
    if not needle:
        raise ValueError("query must not be empty")
    cap = max(1, min(limit, 100))
    async with get_async_client() as client:
        # `limit` here is the page size of each API request, not a result cap
        kwargs: dict[str, Any] = {"limit": 1000}
        if media_type:
            kwargs["media_type"] = media_type
        result = []
        async for item in client.get_files(**kwargs):
            if needle in (getattr(item, "name", None) or "").casefold():
                result.append(_resource_to_dict(item))
                if len(result) >= cap:
                    break
        return result


# ─── Metadata ────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_metadata(path: str) -> dict:
    """Get metadata for a file or folder.

    Args:
        path: Path on Yandex Disk (e.g. "/Documents/file.txt").
    """
    async with get_async_client() as client:
        info = await client.get_meta(path)
        return _resource_to_dict(info)


# ─── Create / delete ──────────────────────────────────────────────────────────

@mcp.tool()
async def create_folder(path: str) -> dict:
    """Create a folder (including intermediate directories).

    Args:
        path: Path of the folder to create (e.g. "/Documents/NewFolder").
    """
    _assert_writable()
    async with get_async_client() as client:
        await client.mkdir(path)
        return {"created": path}


@mcp.tool()
async def delete(path: str, permanently: bool = False) -> dict:
    """Delete a file or folder.

    In safe-delete mode the item is moved to /LEGACY/<YYYY-MM-DD>/<original path>
    instead of being removed, and permanently=True is refused.

    Args:
        path: Path to delete (e.g. "/Documents/old_file.txt").
        permanently: If True, skip trash and delete permanently. Default False.
    """
    _assert_writable()
    if _is_safe_delete():
        return await _safe_delete(path, permanently)
    # H2: prevent accidentally nuking the entire disk root permanently
    normalized = path.rstrip("/") or "/"
    if normalized in ("/", "disk:") and permanently:
        raise ValueError(
            "Permanently deleting the root path '/' is not allowed. "
            "Use permanently=False to move items to Trash instead."
        )
    async with get_async_client() as client:
        await client.remove(path, permanently=permanently)
        return {"deleted": path, "permanently": permanently}


async def _safe_delete(path: str, permanently: bool) -> dict:
    if permanently:
        _refuse_in_safe_delete("Permanent deletion")
    normalized = _normalize_path(path)
    if normalized == "/":
        raise PermissionError("Deleting the disk root is not allowed in safe-delete mode.")
    if _is_inside_legacy(normalized):
        raise PermissionError(
            f"Items inside {LEGACY_ROOT} are removed manually by the disk owner, "
            "not by this server."
        )
    async with get_async_client() as client:
        target = await _legacy_target(client, normalized)
        await _ensure_dir(client, target.rsplit("/", 1)[0])
        await client.move(normalized, target, overwrite=False)
        return {"deleted": path, "moved_to": target, "permanently": False}


# ─── Copy / move ──────────────────────────────────────────────────────────────

@mcp.tool()
async def copy(src: str, dst: str, overwrite: bool = False) -> dict:
    """Copy a file or folder to a new location.

    Args:
        src: Source path (e.g. "/Documents/file.txt").
        dst: Destination path (e.g. "/Archive/file.txt").
        overwrite: Overwrite destination if it exists.
    """
    _assert_writable()
    _assert_no_overwrite(overwrite)
    async with get_async_client() as client:
        await client.copy(src, dst, overwrite=overwrite)
        return {"copied": {"from": src, "to": dst}}


@mcp.tool()
async def move(src: str, dst: str, overwrite: bool = False) -> dict:
    """Move a file or folder to a new location.

    Args:
        src: Source path (e.g. "/Documents/file.txt").
        dst: Destination path (e.g. "/Archive/file.txt").
        overwrite: Overwrite destination if it exists.
    """
    _assert_writable()
    _assert_no_overwrite(overwrite)
    async with get_async_client() as client:
        await client.move(src, dst, overwrite=overwrite)
        return {"moved": {"from": src, "to": dst}}


@mcp.tool()
async def rename(path: str, new_name: str) -> dict:
    """Rename a file or folder (moves it within the same directory).

    Args:
        path: Full path of the item (e.g. "/Documents/old_name.txt").
        new_name: New name without path (e.g. "new_name.txt").
    """
    _assert_writable()
    # L2: reject path separators in the new name to prevent path traversal
    if "/" in new_name or "\\" in new_name:
        raise ValueError(
            f"new_name must not contain path separators ('/' or '\\'): {new_name!r}"
        )
    parent = "/".join(path.rstrip("/").split("/")[:-1]) or "/"
    dst = f"{parent.rstrip('/')}/{new_name}"
    async with get_async_client() as client:
        await client.move(path, dst)
        return {"renamed": {"from": path, "to": dst}}


# ─── Upload / download ────────────────────────────────────────────────────────

@mcp.tool()
async def get_download_url(path: str) -> dict:
    """Get a temporary direct download URL for a file.

    Args:
        path: Path on Yandex Disk (e.g. "/Documents/report.pdf").
    """
    async with get_async_client() as client:
        link = await client.get_download_link(path)
        return {"path": path, "url": link}


@mcp.tool()
async def upload_local_file(local_path: str, disk_path: str, overwrite: bool = False) -> dict:
    """Upload a local file to Yandex Disk (blocking). Use for files under ~100 MB.
    For large files use upload_local_file_background to avoid timeout.

    Args:
        local_path: Absolute path to the file on the local filesystem.
        disk_path: Destination path on Yandex Disk (e.g. "/Videos/video.mp4").
        overwrite: Overwrite if file already exists on Yandex Disk.
    """
    _assert_writable()
    _assert_no_overwrite(overwrite)
    # H1: resolve symlinks and enforce allowlist
    real_path = _check_upload_path(local_path)
    if not os.path.isfile(real_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")
    import aiofiles
    async with get_async_client() as client:
        async with aiofiles.open(real_path, "rb") as f:
            await client.upload(f, disk_path, overwrite=overwrite)
    return {"uploaded": {"from": local_path, "to": disk_path}}


@mcp.tool()
async def upload_local_file_background(
    local_path: str, disk_path: str, overwrite: bool = False
) -> dict:
    """Start uploading a large local file to Yandex Disk in the background.
    Returns immediately with a job_id. Use get_upload_status(job_id) to check progress.
    Suitable for files of any size — no timeout issues.

    Args:
        local_path: Absolute path to the file on the local filesystem.
        disk_path: Destination path on Yandex Disk (e.g. "/Videos/big_video.mp4").
        overwrite: Overwrite if file already exists on Yandex Disk.
    """
    _assert_writable()
    _assert_no_overwrite(overwrite)
    # H1: resolve symlinks and enforce allowlist
    real_path = _check_upload_path(local_path)
    if not os.path.isfile(real_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    # M4: evict stale completed jobs before adding a new one
    _evict_completed_jobs()

    # L3: use full UUID (not truncated) to avoid collisions
    job_id = str(uuid.uuid4())
    file_size = os.path.getsize(real_path)
    filename = os.path.basename(real_path)
    _upload_jobs[job_id] = {
        "status": "uploading",
        "filename": filename,
        "from": local_path,
        "to": disk_path,
        "size": file_size,
        "bytes_uploaded": 0,
        "progress": 0.0,
    }

    async def _do_upload() -> None:
        import aiofiles
        try:
            async with get_async_client() as client:
                async with aiofiles.open(real_path, "rb") as f:
                    pf = _ProgressFile(f, _upload_jobs[job_id])
                    await client.upload(pf, disk_path, overwrite=overwrite)
            _upload_jobs[job_id].update({"status": "done", "progress": 100.0})
        except Exception as e:
            # M2: sanitize error before storing — strip tokens/credentials
            _upload_jobs[job_id]["status"] = "error"
            _upload_jobs[job_id]["error"] = _sanitize_error(e)

    asyncio.create_task(_do_upload())

    return {
        "job_id": job_id,
        "status": "uploading",
        "filename": filename,
        "from": local_path,
        "to": disk_path,
        "size": file_size,
        "hint": f"Check progress with: get_upload_status('{job_id}')",
    }


@mcp.tool()
async def get_upload_status(job_id: str) -> dict:
    """Check the status of a background upload started with upload_local_file_background.

    Args:
        job_id: The job ID returned by upload_local_file_background.
    """
    _assert_writable()
    if job_id not in _upload_jobs:
        return {"error": f"Job '{job_id}' not found"}
    return _upload_jobs[job_id]


@mcp.tool()
async def list_upload_jobs() -> list[dict]:
    """List all background upload jobs and their statuses."""
    _assert_writable()
    return [{"job_id": jid, **info} for jid, info in _upload_jobs.items()]


@mcp.tool()
async def upload_from_url(url: str, path: str, overwrite: bool = False) -> dict:
    """Upload a file to Yandex Disk by downloading it from a remote URL.

    Args:
        url: Source URL to download the file from (must be http or https).
        path: Destination path on Yandex Disk (e.g. "/Downloads/file.zip").
        overwrite: Overwrite if file already exists.
    """
    _assert_writable()
    _assert_no_overwrite(overwrite)
    # M3: reject non-http(s) and localhost/link-local URLs
    _validate_url(url)
    async with get_async_client() as client:
        await client.upload_by_link(url, path, overwrite=overwrite)
        return {"uploaded": {"url": url, "to": path}}


# ─── Sharing / publishing ─────────────────────────────────────────────────────

@mcp.tool()
async def publish(path: str) -> dict:
    """Publish a file or folder and return its public URL.

    Args:
        path: Path on Yandex Disk to publish (e.g. "/Documents/presentation.pdf").
    """
    _assert_writable()
    async with get_async_client() as client:
        await client.publish(path)
        info = await client.get_meta(path)
        return {
            "path": path,
            "public_url": info.public_url,
            "public_key": info.public_key,
        }


@mcp.tool()
async def unpublish(path: str) -> dict:
    """Revoke public access to a file or folder.

    Args:
        path: Path on Yandex Disk (e.g. "/Documents/presentation.pdf").
    """
    _assert_writable()
    async with get_async_client() as client:
        await client.unpublish(path)
        return {"unpublished": path}


@mcp.tool()
async def get_public_resource(public_key: str, path: str = "/", limit: int = 20) -> dict:
    """Get information about a public resource by its public key or URL.

    Args:
        public_key: Public key or public URL of the resource.
        path: Sub-path within a public folder (use "/" for root).
        limit: Max items to list if the resource is a folder.
    """
    async with get_async_client() as client:
        info = await client.get_public_meta(public_key, path=path, limit=limit)
        return _resource_to_dict(info)


# ─── Trash ────────────────────────────────────────────────────────────────────

@mcp.tool()
async def list_trash(limit: int = 20, offset: int = 0) -> list[dict]:
    """List files in the Trash.

    Args:
        limit: Max items to return (1–100).
        offset: Offset for pagination.
    """
    async with get_async_client() as client:
        result = []
        async for item in client.trash_listdir(
            "/",
            limit=min(limit, 100),
            offset=offset,
        ):
            result.append(_resource_to_dict(item))
        return result


@mcp.tool()
async def restore_from_trash(path: str, destination: str | None = None, overwrite: bool = False) -> dict:
    """Restore a file or folder from Trash.

    Args:
        path: Path of the item in Trash (e.g. "/trash/old_file.txt").
        destination: Optional new path to restore to. Uses original path if omitted.
        overwrite: Overwrite if destination already exists.
    """
    _assert_writable()
    _assert_no_overwrite(overwrite)
    async with get_async_client() as client:
        kwargs: dict[str, Any] = {"overwrite": overwrite}
        if destination:
            kwargs["dst_path"] = destination
        await client.restore_trash(path, **kwargs)
        return {"restored": path, "destination": destination or "original location"}


@mcp.tool()
async def empty_trash() -> dict:
    """Permanently delete all files in Trash."""
    _assert_writable()
    _refuse_in_safe_delete("Emptying Trash")
    async with get_async_client() as client:
        await client.remove_trash("/")
        return {"trash": "emptied"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _resource_to_dict(r: Any) -> dict:
    """Convert a yadisk ResourceObject to a plain dict."""
    d: dict[str, Any] = {
        "name": getattr(r, "name", None),
        "path": getattr(r, "path", None),
        "type": getattr(r, "type", None),
        "size": getattr(r, "size", None),
        "created": str(getattr(r, "created", None)),
        "modified": str(getattr(r, "modified", None)),
        "media_type": getattr(r, "media_type", None),
        "mime_type": getattr(r, "mime_type", None),
        "public_url": getattr(r, "public_url", None),
        "public_key": getattr(r, "public_key", None),
    }
    embedded = getattr(r, "embedded", None)
    if embedded is not None:
        items_attr = getattr(embedded, "items", None)
        if items_attr is not None:
            d["items"] = [_resource_to_dict(i) for i in items_attr]
    return {k: v for k, v in d.items() if v is not None}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Yandex Disk MCP Server")
    parser.add_argument(
        "--read-only",
        action="store_true",
        default=False,
        help="Disable all write operations (overrides YADISK_MCP_READ_ONLY env var)",
    )
    parser.add_argument(
        "--safe-delete",
        action="store_true",
        default=False,
        help=(
            "Never destroy data: delete moves items to /LEGACY/<date>/, permanent "
            "deletion, emptying Trash and overwrite=True are refused "
            "(overrides YADISK_MCP_SAFE_DELETE env var)"
        ),
    )
    args = parser.parse_args()
    if args.read_only:
        configure(read_only=True)
    if args.safe_delete:
        configure(safe_delete=True)
    mcp.run()


if __name__ == "__main__":
    main()
