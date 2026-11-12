# yadisk-mcp

[![CI](https://github.com/Patr56/yadisk-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Patr56/yadisk-mcp/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/yadisk-mcp)](https://pypi.org/project/yadisk-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/yadisk-mcp)](https://pypi.org/project/yadisk-mcp/)

MCP server for **Yandex Disk** — manage files, folders, sharing and trash via Claude or any MCP-compatible client.

[Русская версия](README.md)

## Highlights

- ⚡ **Fully async** — all operations are non-blocking; parallel requests work without delays
- 🚀 **Background uploads for large files** — kick off a task and get a `job_id` instantly; check progress and status at any time
- 📊 **Progress tracking** — upload percentage, bytes transferred, and filename for every background job
- 🗂️ **22 tools** — full Yandex Disk API coverage: files, folders, search, sharing, trash

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

You'll need a Yandex OAuth token — see [Getting a Token](#getting-a-token) for instructions.

### Claude Code (CLI)

```bash
claude mcp add yadisk -e YANDEX_DISK_TOKEN=your_token_here -- yadisk-mcp
```

Or manually in `~/.claude.json`:

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
        "command": "yadisk-mcp",
        "env": {
          "YANDEX_DISK_TOKEN": "your_token_here"
        }
      }
    }
  }
}
```

## Read-only mode

Run the server with `--read-only` to disable all write operations — useful for safe browsing or demos.

Three ways to enable, in priority order (explicit beats implicit):

```bash
# 1. CLI flag
yadisk-mcp --read-only

# 2. Environment variable
YADISK_MCP_READ_ONLY=true yadisk-mcp
```

```python
# 3. Programmatic (library use)
from yadisk_mcp.server import configure, mcp
configure(read_only=True)
mcp.run()
```

In Claude Desktop config:

```json
{
  "mcpServers": {
    "yadisk": {
      "command": "yadisk-mcp",
      "args": ["--read-only"],
      "env": {
        "YANDEX_DISK_TOKEN": "your_token_here"
      }
    }
  }
}
```

**Blocked:** `create_folder`, `delete`, `copy`, `move`, `rename`, `upload_local_file`, `upload_local_file_background`, `upload_from_url`, `get_upload_status`, `list_upload_jobs`, `publish`, `unpublish`, `restore_from_trash`, `empty_trash`

**Allowed:** `disk_info`, `list_files`, `list_recent_files`, `search_files`, `get_metadata`, `get_download_url`, `get_public_resource`, `list_trash`

## Safe-delete mode

With `--safe-delete` (or `YADISK_MCP_SAFE_DELETE=true`) the server never destroys data:

- `delete` moves the item to `/LEGACY/<YYYY-MM-DD>/<original path>` instead of removing it. If the target already exists, a `__HHMMSS` suffix is appended.
- `delete(permanently=True)` and `empty_trash` are refused.
- `overwrite=True` is refused in `copy`, `move`, `upload_local_file`, `upload_local_file_background`, `upload_from_url`, `restore_from_trash`.
- Items inside `/LEGACY` are never touched by the server; the disk owner cleans them up manually.

```bash
yadisk-mcp --safe-delete
```

Programmatically: `configure(safe_delete=True)`. Can be combined with `--read-only`.

## Security

### Restricting file uploads

By default, `upload_local_file` and `upload_local_file_background` can upload any local file. To restrict uploads to specific directories, set `YADISK_MCP_UPLOAD_ALLOWED_DIRS`:

```bash
# Allow uploads only from /home/user/uploads and /tmp/exports
YADISK_MCP_UPLOAD_ALLOWED_DIRS=/home/user/uploads,/tmp/exports yadisk-mcp
```

Symlinks pointing outside the allowed directories are automatically blocked.

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
