#!/usr/bin/env python3
"""
Helper script to get a Yandex Disk OAuth token.

Usage:
    python3 get_token.py

Steps:
    1. Create an app at https://oauth.yandex.ru/client/new
       - Platform: Web services
       - Callback URL: https://oauth.yandex.ru/verification_code
       - Permissions: Yandex.Disk REST API (cloud_api:disk.*)
    2. Run this script and enter your Client ID and Client Secret
    3. Follow the link, authorize, paste the code back
"""

import urllib.parse
import urllib.request
import json


def main():
    print("=== Yandex Disk OAuth Token Helper ===\n")
    print("1. Go to https://oauth.yandex.ru/client/new and create an app:")
    print("   - Platform: Web services")
    print("   - Callback URL: https://oauth.yandex.ru/verification_code")
    print("   - Permissions: Yandex.Disk REST API (all cloud_api:disk.* scopes)\n")

    client_id = input("Enter your Client ID: ").strip()
    client_secret = input("Enter your Client Secret: ").strip()

    auth_url = (
        "https://oauth.yandex.ru/authorize"
        f"?response_type=code"
        f"&client_id={urllib.parse.quote(client_id)}"
    )

    print(f"\n2. Open this URL in your browser and authorize:\n   {auth_url}\n")
    code = input("3. Paste the authorization code here: ").strip()

    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
    }).encode()

    req = urllib.request.Request(
        "https://oauth.yandex.ru/token",
        data=data,
        method="POST",
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    token = result.get("access_token")
    if token:
        print(f"\n=== Your token ===")
        print(f"YANDEX_DISK_TOKEN={token}")
        print(
            "\nSecurity reminder:"
            "\n  - Do NOT commit this token to version control."
            "\n  - Do NOT share terminal output that contains this token."
            "\n  - Store it in a .env file (chmod 600) or a secrets manager."
            "\n  - Clear your terminal scrollback after copying the token."
        )
    else:
        print(f"\nError: {result}")


if __name__ == "__main__":
    main()
