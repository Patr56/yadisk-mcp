import pytest
from yadisk_mcp.server import list_files, list_recent_files, search_files
from tests.conftest import async_iter, fake_resource


async def test_list_files_returns_items(patched_client):
    items = [fake_resource(name="a.txt"), fake_resource(name="b.mp4")]
    patched_client.listdir = async_iter(items)

    result = await list_files("/", limit=10)

    assert len(result) == 2
    assert result[0]["name"] == "a.txt"
    patched_client.listdir.assert_called_once_with("/", limit=10, offset=0, sort="name")


async def test_list_files_caps_limit_at_100(patched_client):
    patched_client.listdir = async_iter([])
    await list_files("/", limit=200)
    assert patched_client.listdir.call_args.kwargs["limit"] == 100


async def test_list_recent_files(patched_client):
    patched_client.get_last_uploaded = async_iter([fake_resource(name="new.jpg")])
    result = await list_recent_files(limit=5)
    assert len(result) == 1
    patched_client.get_last_uploaded.assert_called_once_with(limit=5)


async def test_search_files_without_media_type(patched_client):
    patched_client.search = async_iter([fake_resource(name="found.pdf")])
    result = await search_files("report")
    assert result[0]["name"] == "found.pdf"
    assert "media_type" not in patched_client.search.call_args.kwargs


async def test_search_files_with_media_type(patched_client):
    patched_client.search = async_iter([])
    await search_files("holiday", media_type="video")
    assert patched_client.search.call_args.kwargs["media_type"] == "video"
