"""Yandex Disk MCP Server."""

import os
from typing import Any
import yadisk
from mcp.server.fastmcp import FastMCP

TOKEN = os.environ.get("YANDEX_DISK_TOKEN", "")

mcp = FastMCP("yadisk")


def get_client() -> yadisk.Client:
    if not TOKEN:
        raise RuntimeError(
            "YANDEX_DISK_TOKEN environment variable is not set. "
            "Get a token at https://oauth.yandex.ru and set it."
        )
    return yadisk.Client(token=TOKEN)


# ─── Disk info ───────────────────────────────────────────────────────────────

@mcp.tool()
def disk_info() -> dict:
    """Get Yandex Disk quota and usage information."""
    with get_client() as client:
        info = client.get_disk_info()
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
def list_files(
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
    with get_client() as client:
        items = client.listdir(
            path,
            limit=min(limit, 100),
            offset=offset,
            sort=sort,
        )
        result = []
        for item in items:
            result.append(_resource_to_dict(item))
        return result


@mcp.tool()
def list_recent_files(limit: int = 20) -> list[dict]:
    """List recently uploaded files across the entire disk.

    Args:
        limit: Max number of files to return (1–100).
    """
    with get_client() as client:
        items = client.get_last_uploaded(limit=min(limit, 100))
        return [_resource_to_dict(item) for item in items]


@mcp.tool()
def search_files(query: str, limit: int = 20, media_type: str | None = None) -> list[dict]:
    """Search for files on Yandex Disk by name.

    Args:
        query: Search query string.
        limit: Max results (1–100).
        media_type: Optional media type filter: audio, backup, book, compressed,
                    data, development, disk_image, document, encoded, executable,
                    flash, font, image, msi, text, unknown, video, web.
    """
    with get_client() as client:
        kwargs: dict[str, Any] = {"limit": min(limit, 100)}
        if media_type:
            kwargs["media_type"] = media_type
        items = client.search(query, **kwargs)
        return [_resource_to_dict(item) for item in items]


# ─── Metadata ────────────────────────────────────────────────────────────────

@mcp.tool()
def get_metadata(path: str) -> dict:
    """Get metadata for a file or folder.

    Args:
        path: Path on Yandex Disk (e.g. "/Documents/file.txt").
    """
    with get_client() as client:
        info = client.get_meta(path)
        return _resource_to_dict(info)


# ─── Create / delete ──────────────────────────────────────────────────────────

@mcp.tool()
def create_folder(path: str) -> dict:
    """Create a folder (including intermediate directories).

    Args:
        path: Path of the folder to create (e.g. "/Documents/NewFolder").
    """
    with get_client() as client:
        client.mkdir(path)
        return {"created": path}


@mcp.tool()
def delete(path: str, permanently: bool = False) -> dict:
    """Delete a file or folder.

    Args:
        path: Path to delete (e.g. "/Documents/old_file.txt").
        permanently: If True, skip trash and delete permanently. Default False.
    """
    with get_client() as client:
        client.remove(path, permanently=permanently)
        return {"deleted": path, "permanently": permanently}


# ─── Copy / move ──────────────────────────────────────────────────────────────

@mcp.tool()
def copy(src: str, dst: str, overwrite: bool = False) -> dict:
    """Copy a file or folder to a new location.

    Args:
        src: Source path (e.g. "/Documents/file.txt").
        dst: Destination path (e.g. "/Archive/file.txt").
        overwrite: Overwrite destination if it exists.
    """
    with get_client() as client:
        client.copy(src, dst, overwrite=overwrite)
        return {"copied": {"from": src, "to": dst}}


@mcp.tool()
def move(src: str, dst: str, overwrite: bool = False) -> dict:
    """Move a file or folder to a new location.

    Args:
        src: Source path (e.g. "/Documents/file.txt").
        dst: Destination path (e.g. "/Archive/file.txt").
        overwrite: Overwrite destination if it exists.
    """
    with get_client() as client:
        client.move(src, dst, overwrite=overwrite)
        return {"moved": {"from": src, "to": dst}}


@mcp.tool()
def rename(path: str, new_name: str) -> dict:
    """Rename a file or folder (moves it within the same directory).

    Args:
        path: Full path of the item (e.g. "/Documents/old_name.txt").
        new_name: New name without path (e.g. "new_name.txt").
    """
    parent = "/".join(path.rstrip("/").split("/")[:-1]) or "/"
    dst = f"{parent.rstrip('/')}/{new_name}"
    with get_client() as client:
        client.move(path, dst)
        return {"renamed": {"from": path, "to": dst}}


# ─── Upload / download ────────────────────────────────────────────────────────

@mcp.tool()
def get_download_url(path: str) -> dict:
    """Get a temporary direct download URL for a file.

    Args:
        path: Path on Yandex Disk (e.g. "/Documents/report.pdf").
    """
    with get_client() as client:
        link = client.get_download_link(path)
        return {"path": path, "url": link}


@mcp.tool()
def upload_local_file(local_path: str, disk_path: str, overwrite: bool = False) -> dict:
    """Upload a local file from the server's filesystem to Yandex Disk.

    Args:
        local_path: Absolute path to the file on the local filesystem (e.g. "/home/user/video.mp4").
        disk_path: Destination path on Yandex Disk (e.g. "/Videos/video.mp4").
        overwrite: Overwrite if file already exists on Yandex Disk.
    """
    import os
    if not os.path.isfile(local_path):
        raise FileNotFoundError(f"Local file not found: {local_path}")
    with get_client() as client:
        client.upload(local_path, disk_path, overwrite=overwrite)
    return {"uploaded": {"from": local_path, "to": disk_path}}


@mcp.tool()
def upload_from_url(url: str, path: str, overwrite: bool = False) -> dict:
    """Upload a file to Yandex Disk by downloading it from a remote URL.

    Args:
        url: Source URL to download the file from.
        path: Destination path on Yandex Disk (e.g. "/Downloads/file.zip").
        overwrite: Overwrite if file already exists.
    """
    with get_client() as client:
        client.upload_by_link(url, path, overwrite=overwrite)
        return {"uploaded": {"url": url, "to": path}}


# ─── Sharing / publishing ─────────────────────────────────────────────────────

@mcp.tool()
def publish(path: str) -> dict:
    """Publish a file or folder and return its public URL.

    Args:
        path: Path on Yandex Disk to publish (e.g. "/Documents/presentation.pdf").
    """
    with get_client() as client:
        client.publish(path)
        info = client.get_meta(path)
        return {
            "path": path,
            "public_url": info.public_url,
            "public_key": info.public_key,
        }


@mcp.tool()
def unpublish(path: str) -> dict:
    """Revoke public access to a file or folder.

    Args:
        path: Path on Yandex Disk (e.g. "/Documents/presentation.pdf").
    """
    with get_client() as client:
        client.unpublish(path)
        return {"unpublished": path}


@mcp.tool()
def get_public_resource(public_key: str, path: str = "/", limit: int = 20) -> dict:
    """Get information about a public resource by its public key or URL.

    Args:
        public_key: Public key or public URL of the resource.
        path: Sub-path within a public folder (use "/" for root).
        limit: Max items to list if the resource is a folder.
    """
    with get_client() as client:
        info = client.get_public_meta(public_key, path=path, limit=limit)
        return _resource_to_dict(info)


# ─── Trash ────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_trash(limit: int = 20, offset: int = 0) -> list[dict]:
    """List files in the Trash.

    Args:
        limit: Max items to return (1–100).
        offset: Offset for pagination.
    """
    with get_client() as client:
        items = client.trash_listdir(
            "/",
            limit=min(limit, 100),
            offset=offset,
        )
        return [_resource_to_dict(item) for item in items]


@mcp.tool()
def restore_from_trash(path: str, destination: str | None = None, overwrite: bool = False) -> dict:
    """Restore a file or folder from Trash.

    Args:
        path: Path of the item in Trash (e.g. "/trash/old_file.txt").
        destination: Optional new path to restore to. Uses original path if omitted.
        overwrite: Overwrite if destination already exists.
    """
    with get_client() as client:
        kwargs: dict[str, Any] = {"overwrite": overwrite}
        if destination:
            kwargs["dst_path"] = destination
        client.restore_trash(path, **kwargs)
        return {"restored": path, "destination": destination or "original location"}


@mcp.tool()
def empty_trash() -> dict:
    """Permanently delete all files in Trash."""
    with get_client() as client:
        client.remove_trash("/")
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
    # Embed sub-items if directory listing included them
    embedded = getattr(r, "embedded", None)
    if embedded is not None:
        items_attr = getattr(embedded, "items", None)
        if items_attr is not None:
            d["items"] = [_resource_to_dict(i) for i in items_attr]
    return {k: v for k, v in d.items() if v is not None}


if __name__ == "__main__":
    mcp.run()
