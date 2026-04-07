from yadisk_mcp.server import create_folder, delete, copy, move, rename


async def test_create_folder(patched_client):
    result = await create_folder("/Documents/NewFolder")
    assert result == {"created": "/Documents/NewFolder"}
    patched_client.mkdir.assert_called_once_with("/Documents/NewFolder")


async def test_delete_to_trash(patched_client):
    result = await delete("/old_file.txt")
    assert result["permanently"] is False
    patched_client.remove.assert_called_once_with("/old_file.txt", permanently=False)


async def test_delete_permanently(patched_client):
    result = await delete("/old_file.txt", permanently=True)
    assert result["permanently"] is True
    patched_client.remove.assert_called_once_with("/old_file.txt", permanently=True)


async def test_copy(patched_client):
    result = await copy("/src/file.txt", "/dst/file.txt")
    assert result == {"copied": {"from": "/src/file.txt", "to": "/dst/file.txt"}}
    patched_client.copy.assert_called_once_with("/src/file.txt", "/dst/file.txt", overwrite=False)


async def test_move(patched_client):
    result = await move("/old/file.txt", "/new/file.txt", overwrite=True)
    assert result == {"moved": {"from": "/old/file.txt", "to": "/new/file.txt"}}
    patched_client.move.assert_called_once_with("/old/file.txt", "/new/file.txt", overwrite=True)


async def test_rename(patched_client):
    result = await rename("/Documents/old_name.txt", "new_name.txt")
    assert result["renamed"]["to"] == "/Documents/new_name.txt"
    patched_client.move.assert_called_once_with(
        "/Documents/old_name.txt", "/Documents/new_name.txt"
    )


async def test_rename_root_file(patched_client):
    # File at root: /old.txt -> /new.txt
    result = await rename("/old.txt", "new.txt")
    assert result["renamed"]["to"] == "/new.txt"
