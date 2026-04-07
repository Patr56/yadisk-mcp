from unittest.mock import MagicMock
from yadisk_mcp.server import disk_info


async def test_disk_info_returns_correct_fields(patched_client):
    info = MagicMock()
    info.total_space = 100
    info.used_space = 40
    info.trash_size = 5
    info.user.login = "test@yandex.ru"
    info.user.display_name = "Test User"
    patched_client.get_disk_info.return_value = info

    result = await disk_info()

    assert result["total_space"] == 100
    assert result["used_space"] == 40
    assert result["trash_size"] == 5
    assert result["free_space"] == 60
    assert result["user"]["login"] == "test@yandex.ru"


async def test_disk_info_no_user(patched_client):
    info = MagicMock()
    info.total_space = 50
    info.used_space = 10
    info.trash_size = 0
    info.user = None
    patched_client.get_disk_info.return_value = info

    result = await disk_info()
    assert result["user"]["login"] is None
