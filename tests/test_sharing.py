from tests.conftest import fake_resource
from yadisk_mcp.server import publish, unpublish, get_public_resource


async def test_publish(patched_client):
    meta = fake_resource(
        public_url="https://disk.yandex.ru/d/abc123",
        public_key="abc123",
    )
    patched_client.get_meta.return_value = meta

    result = await publish("/Documents/presentation.pdf")

    patched_client.publish.assert_called_once_with("/Documents/presentation.pdf")
    assert result["public_url"] == "https://disk.yandex.ru/d/abc123"
    assert result["public_key"] == "abc123"


async def test_unpublish(patched_client):
    result = await unpublish("/Documents/presentation.pdf")
    assert result == {"unpublished": "/Documents/presentation.pdf"}
    patched_client.unpublish.assert_called_once_with("/Documents/presentation.pdf")


async def test_get_public_resource(patched_client):
    patched_client.get_public_meta.return_value = fake_resource(
        name="shared_folder", type="dir"
    )
    result = await get_public_resource("abc123")
    assert result["type"] == "dir"
    patched_client.get_public_meta.assert_called_once_with("abc123", path="/", limit=20)
