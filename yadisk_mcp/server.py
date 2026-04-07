"""Yandex Disk MCP Server."""

import os
import uuid
import asyncio
from typing import Any
import yadisk
from mcp.server.fastmcp import FastMCP

TOKEN = os.environ.get("YANDEX_DISK_TOKEN", "")

mcp = FastMCP("yadisk")

# ─── Background upload jobs ───────────────────────────────────────────────────
_upload_jobs: dict[str, dict] = {}


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


def get_async_client() -> yadisk.AsyncClient:
    if not TOKEN:
        raise RuntimeError(
            "YANDEX_DISK_TOKEN environment variable is not set. "
            "Get a token at https://oauth.yandex.ru and set it."
        )
    return yadisk.AsyncClient(token=TOKEN)


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
        result = []
        async for item in client.get_last_uploaded(limit=min(limit, 100)):
            result.append(_resource_to_dict(item))
        return result


@mcp.tool()
async def search_files(query: str, limit: int = 20, media_type: str | None = None) -> list[dict]:
    """Search for files on Yandex Disk by name.

    Args:
        query: Search query string.
        limit: Max results (1–100).
        media_type: Optional media type filter: audio, backup, book, compressed,
                    data, development, disk_image, document, encoded, executable,
                    flash, font, image, msi, text, unknown, video, web.
    """
    async with get_async_client() as client:
        kwargs: dict[str, Any] = {"limit": min(limit, 100)}
        if media_type:
            kwargs["media_type"] = media_type
        result = []
        async for item in client.search(query, **kwargs):
            result.append(_resource_to_dict(item))
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
    async with get_async_client() as client:
        await client.mkdir(path)
        return {"created": path}


@mcp.tool()
async def delete(path: str, permanently: bool = False) -> dict:
    """Delete a file or folder.

    Args:
        path: Path to delete (e.g. "/Documents/old_file.txt").
        permanently: If True, skip trash and delete permanently. Default False.
    """
    async with get_async_client() as client:
        await client.remove(path, permanently=permanently)
        return {"deleted": path, "permanently": permanently}


# ─── Copy / move ──────────────────────────────────────────────────────────────

@mcp.tool()
async def copy(src: str, dst: str, overwrite: bool = False) -> dict:
    """Copy a file or folder to a new location.

    Args:
        src: Source path (e.g. "/Documents/file.txt").
        dst: Destination path (e.g. "/Archive/file.txt").
        overwrite: Overwrite destination if it exists.
    """
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
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")
    import aiofiles
    async with get_async_client() as client:
        async with aiofiles.open(local_path, "rb") as f:
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
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")

    job_id = str(uuid.uuid4())[:8]
    file_size = os.path.getsize(local_path)
    filename = os.path.basename(local_path)
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
                async with aiofiles.open(local_path, "rb") as f:
                    pf = _ProgressFile(f, _upload_jobs[job_id])
                    await client.upload(pf, disk_path, overwrite=overwrite)
            _upload_jobs[job_id].update({"status": "done", "progress": 100.0})
        except Exception as e:
            _upload_jobs[job_id]["status"] = "error"
            _upload_jobs[job_id]["error"] = str(e)

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
    if job_id not in _upload_jobs:
        return {"error": f"Job '{job_id}' not found"}
    return _upload_jobs[job_id]


@mcp.tool()
async def list_upload_jobs() -> list[dict]:
    """List all background upload jobs and their statuses."""
    return [{"job_id": jid, **info} for jid, info in _upload_jobs.items()]


@mcp.tool()
async def upload_from_url(url: str, path: str, overwrite: bool = False) -> dict:
    """Upload a file to Yandex Disk by downloading it from a remote URL.

    Args:
        url: Source URL to download the file from.
        path: Destination path on Yandex Disk (e.g. "/Downloads/file.zip").
        overwrite: Overwrite if file already exists.
    """
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
    async with get_async_client() as client:
        kwargs: dict[str, Any] = {"overwrite": overwrite}
        if destination:
            kwargs["dst_path"] = destination
        await client.restore_trash(path, **kwargs)
        return {"restored": path, "destination": destination or "original location"}


@mcp.tool()
async def empty_trash() -> dict:
    """Permanently delete all files in Trash."""
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


if __name__ == "__main__":
    mcp.run()
