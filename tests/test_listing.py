import pytest
from unittest.mock import AsyncMock
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
    # yadisk>=3: AsyncClient.get_last_uploaded is a coroutine returning a list,
    # not an async generator.
    patched_client.get_last_uploaded = AsyncMock(return_value=[fake_resource(name="new.jpg")])
    result = await list_recent_files(limit=5)
    assert len(result) == 1
    assert result[0]["name"] == "new.jpg"
    patched_client.get_last_uploaded.assert_awaited_once_with(limit=5)


async def test_list_recent_files_caps_limit_at_100(patched_client):
    patched_client.get_last_uploaded = AsyncMock(return_value=[])
    await list_recent_files(limit=500)
    assert patched_client.get_last_uploaded.call_args.kwargs["limit"] == 100


# The Yandex Disk REST API has no search endpoint; search_files scans the flat
# file list (AsyncClient.get_files, an async generator) and filters by name.

async def test_search_files_matches_name_case_insensitive(patched_client):
    patched_client.get_files = async_iter([
        fake_resource(name="Q3_Report.pdf"),
        fake_resource(name="other.txt"),
        fake_resource(name="report-final.docx"),
    ])
    result = await search_files("REPORT")
    assert [r["name"] for r in result] == ["Q3_Report.pdf", "report-final.docx"]


async def test_search_files_matches_cyrillic(patched_client):
    patched_client.get_files = async_iter([
        fake_resource(name="Презентация ЧАЙ 2026.pdf"),
        fake_resource(name="кофе.pdf"),
    ])
    result = await search_files("чай")
    assert [r["name"] for r in result] == ["Презентация ЧАЙ 2026.pdf"]


async def test_search_files_stops_at_limit(patched_client):
    patched_client.get_files = async_iter(
        [fake_resource(name=f"tea_{i}.pdf") for i in range(10)]
    )
    result = await search_files("tea", limit=3)
    assert len(result) == 3


async def test_search_files_without_media_type(patched_client):
    patched_client.get_files = async_iter([fake_resource(name="found.pdf")])
    result = await search_files("found")
    assert result[0]["name"] == "found.pdf"
    assert "media_type" not in patched_client.get_files.call_args.kwargs


async def test_search_files_with_media_type(patched_client):
    patched_client.get_files = async_iter([])
    await search_files("holiday", media_type="video")
    assert patched_client.get_files.call_args.kwargs["media_type"] == "video"


async def test_search_files_rejects_empty_query(patched_client):
    patched_client.get_files = async_iter([])
    with pytest.raises(ValueError):
        await search_files("   ")
    patched_client.get_files.assert_not_called()
