# yadisk-mcp

MCP server for **Yandex Disk** — manage files, folders, sharing, and trash via Claude or any MCP-compatible client.

## Features

| Tool | Description |
|------|-------------|
| `disk_info` | Quota, used/free space, user info |
| `list_files` | List directory contents with sorting and pagination |
| `list_recent_files` | Recently uploaded files |
| `search_files` | Search by name with optional media type filter |
| `get_metadata` | Metadata for any file or folder |
| `create_folder` | Create folder (with intermediate dirs) |
| `delete` | Move to Trash or permanently delete |
| `copy` | Copy file/folder |
| `move` | Move file/folder |
| `rename` | Rename file/folder |
| `get_download_url` | Get a direct temporary download link |
| `upload_from_url` | Upload a file from a remote URL |
| `publish` | Publish and get public URL |
| `unpublish` | Revoke public access |
| `get_public_resource` | Inspect a public resource by key/URL |
| `list_trash` | List Trash contents |
| `restore_from_trash` | Restore item from Trash |
| `empty_trash` | Empty Trash permanently |

## Getting a Token

Run the helper script (no extra dependencies needed):

```bash
python3 get_token.py
```

Or do it manually:
1. Go to [oauth.yandex.ru](https://oauth.yandex.ru/client/new) and create an app
2. Platform: **Web services**, Callback URL: `https://oauth.yandex.ru/verification_code`
3. Permissions: **Yandex.Disk REST API** (all `cloud_api:disk.*` scopes)
4. Get a token via the OAuth flow

## Installation

```bash
pip install yadisk-mcp
```

Or from source:

```bash
git clone https://github.com/phoroshilov/yadisk-mcp
cd yadisk-mcp
pip install -e .
```

## Configuration

### Claude Code

Add to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "yadisk": {
      "command": "python3",
      "args": ["-m", "yadisk_mcp.server"],
      "env": {
        "YANDEX_DISK_TOKEN": "your_token_here"
      }
    }
  }
}
```

Or if installed via pip (uses the `yadisk-mcp` script):

```json
{
  "mcpServers": {
    "yadisk": {
      "command": "yadisk-mcp",
      "env": {
        "YANDEX_DISK_TOKEN": "your_token_here"
      }
    }
  }
}
```

### Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "yadisk": {
      "command": "yadisk-mcp",
      "env": {
        "YANDEX_DISK_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Usage Examples

Once configured, Claude can use commands like:

> "Show me what's in my Yandex Disk root folder"  
> "Create a folder /Backups/2026-04"  
> "Move all files from /Downloads to /Archive"  
> "Publish /Documents/presentation.pdf and give me the link"  
> "Empty the trash"  
> "Search for all PDF files"

## License

MIT
