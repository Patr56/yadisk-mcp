from tests.conftest import async_iter, fake_resource
from yadisk_mcp.server import list_trash, restore_from_trash, empty_trash


async def test_list_trash(patched_client):
    patched_client.trash_listdir = async_iter(
        [fake_resource(name="deleted.txt"), fake_resource(name="old.jpg")]
    )
    result = await list_trash(limit=10)
    assert len(result) == 2
    patched_client.trash_listdir.assert_called_once_with("/", limit=10, offset=0)


async def test_restore_from_trash_default_location(patched_client):
    result = await restore_from_trash("/trash/file.txt")
    assert result["destination"] == "original location"
    patched_client.restore_trash.assert_called_once_with(
        "/trash/file.txt", overwrite=False
    )


async def test_restore_from_trash_custom_destination(patched_client):
    result = await restore_from_trash("/trash/file.txt", destination="/Archive/file.txt")
    assert result["destination"] == "/Archive/file.txt"
    patched_client.restore_trash.assert_called_once_with(
        "/trash/file.txt", overwrite=False, dst_path="/Archive/file.txt"
    )


async def test_empty_trash(patched_client):
    result = await empty_trash()
    assert result == {"trash": "emptied"}
    patched_client.remove_trash.assert_called_once_with("/")
