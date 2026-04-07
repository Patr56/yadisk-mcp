# yadisk-mcp

[![CI](https://github.com/Patr56/yadisk-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/Patr56/yadisk-mcp/actions/workflows/ci.yml)

MCP-сервер для **Яндекс Диска** — управляй файлами, папками, публикацией и корзиной через Claude или любой MCP-совместимый клиент.

[English version](README_EN.md)

## Особенности

- **Полностью асинхронный** — все операции неблокирующие, параллельные запросы работают без задержек
- **Фоновая загрузка больших файлов** — отправь задачу и сразу получи `job_id`; прогресс и статус доступны в любой момент
- **Трекинг прогресса** — процент выполнения, загружено байт, имя файла для каждой фоновой задачи
- **22 инструмента** — полное покрытие API Яндекс Диска: файлы, папки, поиск, публикация, корзина
- **Протестирован** — юнит-тесты для всех инструментов, CI на Python 3.11 и 3.12

## Инструменты

### Информация и поиск

| Инструмент | Описание |
|---|---|
| `disk_info` | Квота, использованное/свободное место, данные пользователя |
| `list_files` | Список файлов в папке с сортировкой и пагинацией |
| `list_recent_files` | Последние загруженные файлы |
| `search_files` | Поиск по имени с фильтром по типу медиа |
| `get_metadata` | Метаданные файла или папки |

### Файловые операции

| Инструмент | Описание |
|---|---|
| `create_folder` | Создать папку (включая промежуточные) |
| `delete` | Переместить в корзину или удалить насовсем |
| `copy` | Копировать файл/папку |
| `move` | Переместить файл/папку |
| `rename` | Переименовать файл/папку |

### Загрузка и скачивание

| Инструмент | Описание |
|---|---|
| `upload_local_file` | Загрузить локальный файл на Диск (до ~100 МБ) |
| `upload_local_file_background` | Загрузить большой файл в фоне — возвращает `job_id` мгновенно |
| `get_upload_status` | Проверить статус фоновой загрузки (%, байты, имя файла) |
| `list_upload_jobs` | Список всех активных/завершённых загрузок |
| `upload_from_url` | Загрузить файл по URL |
| `get_download_url` | Получить прямую ссылку на скачивание |

### Публикация

| Инструмент | Описание |
|---|---|
| `publish` | Опубликовать файл/папку и получить публичную ссылку |
| `unpublish` | Закрыть публичный доступ |
| `get_public_resource` | Информация о публичном ресурсе по ключу или ссылке |

### Корзина

| Инструмент | Описание |
|---|---|
| `list_trash` | Список файлов в корзине |
| `restore_from_trash` | Восстановить файл из корзины |
| `empty_trash` | Очистить корзину |

## Получение токена

### Шаг 1 — Создай OAuth-приложение на Яндексе

1. Зайди на [oauth.yandex.ru](https://oauth.yandex.ru) → **Создать приложение** → **Для авторизации пользователей**
2. Введи любое название, загрузи иконку (обязательно)
3. На шаге **Платформы** выбери **Веб-сервисы**, Callback URL:
   ```
   https://oauth.yandex.ru/verification_code
   ```
4. На шаге **Права** в поле **Дополнительные** добавь по одному:
   - `cloud_api:disk.read`
   - `cloud_api:disk.write`
   - `cloud_api:disk.app_folder`
   - `cloud_api:disk.info`
5. Завершил — получишь **Client ID** и **Client Secret**

### Шаг 2 — Получи токен

Открой в браузере (замени `<CLIENT_ID>` на свой):

```
https://oauth.yandex.ru/authorize?response_type=code&client_id=<CLIENT_ID>
```

Авторизуй приложение, получи **код** и обменяй его на токен:

```bash
curl -X POST https://oauth.yandex.ru/token \
  -d "grant_type=authorization_code" \
  -d "code=<CODE>" \
  -d "client_id=<CLIENT_ID>" \
  -d "client_secret=<CLIENT_SECRET>"
```

Используй `access_token` из ответа как `YANDEX_DISK_TOKEN`. Токен действует **1 год**.

### Вспомогательный скрипт

```bash
python3 get_token.py
```

## Установка

```bash
pip install yadisk-mcp
```

Или из исходников:

```bash
git clone https://github.com/Patr56/yadisk-mcp
cd yadisk-mcp
pip install -e .
```

## Настройка

### Claude Code (CLI)

```bash
claude mcp add yadisk -e YANDEX_DISK_TOKEN=your_token_here -- python3 -m yadisk_mcp.server
```

Или вручную в `~/.claude.json`:

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

В `claude_desktop_config.json`:

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

### OpenClaw / другой агент

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

## Примеры использования

После настройки можно говорить Claude:

> «Покажи что у меня на Яндекс Диске»
> «Создай папку /Бэкапы/2026-04»
> «Загрузи файл /home/user/video.mp4 на диск в папку /Видео»
> «Опубликуй /Документы/презентация.pdf и дай ссылку»
> «Загрузи большой файл в фоне и сообщи когда закончится»
> «Очисти корзину»
> «Найди все PDF-файлы»

## Лицензия

MIT
