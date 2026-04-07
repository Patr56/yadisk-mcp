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

### Step 1 — Create a Yandex OAuth app

1. Go to [oauth.yandex.ru](https://oauth.yandex.ru) → **Create app** → choose **"For authorizing users"**
2. Fill in a name (anything, e.g. `yadisk-mcp`) and upload any icon (required)
3. On the **Platforms** step select **Web services** and set Callback URL to:
   ```
   https://oauth.yandex.ru/verification_code
   ```
4. On the **Permissions** step, in the **Additional** field add these scopes one by one:
   - `cloud_api:disk.read`
   - `cloud_api:disk.write`
   - `cloud_api:disk.app_folder`
   - `cloud_api:disk.info`
5. Complete the wizard — you'll get a **Client ID** and **Client Secret**

### Step 2 — Get the token

Open this URL in your browser (replace `<CLIENT_ID>` with your Client ID):

```
https://oauth.yandex.ru/authorize?response_type=code&client_id=<CLIENT_ID>
```

Authorize the app. You'll receive a short **code**.

Then exchange it for a token:

```bash
curl -X POST https://oauth.yandex.ru/token \
  -d "grant_type=authorization_code" \
  -d "code=<CODE>" \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>"
```

The response contains `access_token` — use that as `YANDEX_DISK_TOKEN`.

The token is valid for **1 year**. To refresh it, repeat Step 2 or use the `refresh_token` from the same response.

### Helper script

Alternatively, run the bundled interactive helper (no extra dependencies):

```bash
python3 get_token.py
```

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
