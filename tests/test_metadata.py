from yadisk_mcp.server import get_metadata
from tests.conftest import fake_resource


async def test_get_metadata(patched_client):
    patched_client.get_meta.return_value = fake_resource(
        name="report.pdf", path="/Documents/report.pdf", type="file", size=204800
    )
    result = await get_metadata("/Documents/report.pdf")

    assert result["name"] == "report.pdf"
    assert result["type"] == "file"
    assert result["size"] == 204800
    patched_client.get_meta.assert_called_once_with("/Documents/report.pdf")
