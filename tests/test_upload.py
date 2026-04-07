import asyncio
import pytest
from yadisk_mcp.server import (
    upload_local_file,
    upload_local_file_background,
    upload_from_url,
    get_download_url,
    get_upload_status,
    list_upload_jobs,
    _upload_jobs,
)


async def test_upload_local_file(patched_client, tmp_path):
    f = tmp_path / "video.mp4"
    f.write_bytes(b"fake video data")

    result = await upload_local_file(str(f), "/Videos/video.mp4")
    assert result["uploaded"]["from"] == str(f)
    assert result["uploaded"]["to"] == "/Videos/video.mp4"
    patched_client.upload.assert_called_once()


async def test_upload_local_file_not_found(patched_client):
    with pytest.raises(FileNotFoundError):
        await upload_local_file("/nonexistent/file.mp4", "/Videos/file.mp4")


async def test_upload_local_file_background_returns_immediately(patched_client, tmp_path):
    f = tmp_path / "big.mp4"
    f.write_bytes(b"x" * 1024)

    result = await upload_local_file_background(str(f), "/Videos/big.mp4")

    assert "job_id" in result
    assert result["status"] == "uploading"
    assert result["filename"] == "big.mp4"
    assert result["size"] == 1024


async def test_upload_local_file_background_completes(patched_client, tmp_path):
    f = tmp_path / "test.bin"
    f.write_bytes(b"data")

    result = await upload_local_file_background(str(f), "/test.bin")
    job_id = result["job_id"]

    # Let the background task finish
    await asyncio.sleep(0.1)

    status = await get_upload_status(job_id)
    assert status["status"] == "done"
    assert status["progress"] == 100.0
    assert status["filename"] == "test.bin"


async def test_upload_local_file_background_not_found(patched_client):
    with pytest.raises(FileNotFoundError):
        await upload_local_file_background("/no/such/file.mp4", "/remote.mp4")


async def test_get_upload_status_unknown_job():
    result = await get_upload_status("nonexistent")
    assert "error" in result


async def test_list_upload_jobs_includes_all(patched_client, tmp_path):
    _upload_jobs.clear()
    f = tmp_path / "a.bin"
    f.write_bytes(b"aaa")

    r = await upload_local_file_background(str(f), "/a.bin")
    jobs = await list_upload_jobs()

    assert any(j["job_id"] == r["job_id"] for j in jobs)


async def test_upload_from_url(patched_client):
    result = await upload_from_url("https://example.com/file.zip", "/Downloads/file.zip")
    assert result["uploaded"]["url"] == "https://example.com/file.zip"
    patched_client.upload_by_link.assert_called_once_with(
        "https://example.com/file.zip", "/Downloads/file.zip", overwrite=False
    )


async def test_get_download_url(patched_client):
    patched_client.get_download_link.return_value = "https://downloader.yandex.net/xyz"
    result = await get_download_url("/Documents/report.pdf")
    assert result["url"] == "https://downloader.yandex.net/xyz"
    assert result["path"] == "/Documents/report.pdf"
