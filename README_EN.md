# yadisk-mcp

[![CI](https://github.com/Patr56/yadisk-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Patr56/yadisk-mcp/actions/workflows/ci.yml)

MCP server for **Yandex Disk** — manage files, folders, sharing and trash via Claude or any MCP-compatible client.

[Русская версия](README.md)

## Tools

### Info & Search

| Tool | Description |
|---|---|
| `disk_info` | Quota, used/free space, user info |
| `list_files` | List files in a folder with sorting and pagination |
| `list_recent_files` | Recently uploaded files |
| `search_files` | Search by name with media type filter |
| `get_metadata` | File or folder metadata |

### File Operations

| Tool | Description |
|---|---|
| `create_folder` | Create a folder (including intermediate directories) |
| `delete` | Move to trash or permanently delete |
| `copy` | Copy file/folder |
| `move` | Move file/folder |
| `rename` | Rename file/folder |

### Upload & Download

| Tool | Description |
|---|---|
| `upload_local_file` | Upload a local file to Disk (up to ~100 MB) |
| `upload_local_file_background` | Upload a large file in background — returns `job_id` instantly |
| `get_upload_status` | Check background upload status (%, bytes, filename) |
| `list_upload_jobs` | List all active/completed uploads |
| `upload_from_url` | Upload a file from URL |
| `get_download_url` | Get a direct download link |

### Sharing

| Tool | Description |
|---|---|
| `publish` | Publish file/folder and get a public link |
| `unpublish` | Revoke public access |
| `get_public_resource` | Info about a public resource by key or link |

### Trash

| Tool | Description |
|---|---|
| `list_trash` | List files in trash |
| `restore_from_trash` | Restore a file from trash |
| `empty_trash` | Empty the trash |

## Getting a Token

### Step 1 — Create an OAuth app on Yandex

1. Go to [oauth.yandex.ru](https://oauth.yandex.ru) → **Create application** → **For user authorization**
2. Enter any name, upload an icon (required)
3. On the **Platforms** step, select **Web services**, Callback URL:
   ```
   https://oauth.yandex.ru/verification_code
   ```
4. On the **Permissions** step, add one by one under **Additional**:
   - `cloud_api:disk.read`
   - `cloud_api:disk.write`
   - `cloud_api:disk.app_folder`
   - `cloud_api:disk.info`
5. Finish — you'll receive a **Client ID** and **Client Secret**

### Step 2 — Get the token

Open in browser (replace `<CLIENT_ID>` with yours):

```
https://oauth.yandex.ru/authorize?response_type=code&client_id=<CLIENT_ID>
```

Authorize the app, get the **code** and exchange it for a token:

```bash
curl -X POST https://oauth.yandex.ru/token \
  -d "grant_type=authorization_code" \
  -d "code=<CODE>" \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>"
```

Use `access_token` from the response as `YANDEX_DISK_TOKEN`. The token is valid for **1 year**.

### Helper script

```bash
python3 get_token.py
```

## Installation

```bash
pip install yadisk-mcp
```

Or from source:

```bash
git clone https://github.com/Patr56/yadisk-mcp
cd yadisk-mcp
pip install -e .
```

## Configuration

### Claude Code (CLI)

```bash
claude mcp add yadisk -e YANDEX_DISK_TOKEN=your_token_here -- python3 -m yadisk_mcp.server
```

Or manually in `~/.claude.json`:

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

### Claude Desktop

In `claude_desktop_config.json`:

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

### OpenClaw / Other agents

```json
{
  "mcp": {
    "servers": {
      "yadisk": {
        "command": "python3",
        "args": ["-m", "yadisk_mcp.server"],
        "env": {
          "YANDEX_DISK_TOKEN": "your_token_here"
        }
      }
    }
  }
}
```

## Usage Examples

After setup, you can tell Claude:

> "Show me what's on my Yandex Disk"
> "Create folder /Backups/2026-04"
> "Upload /home/user/video.mp4 to /Videos on disk"
> "Publish /Documents/presentation.pdf and give me the link"
> "Upload a large file in background and notify me when done"
> "Empty the trash"
> "Find all PDF files"

## License

MIT
