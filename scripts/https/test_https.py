"""
Quick HTTPS smoke test for local development.
Ignores certificate validation for convenience.
"""

import json
import ssl
import urllib.request


ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

try:
    with urllib.request.urlopen(
        "https://localhost:8000/api/v1/health", context=ssl_context, timeout=5
    ) as response:
        body = response.read().decode("utf-8")
        print(f"Status: {response.status}")
        try:
            print(json.dumps(json.loads(body), indent=2))
        except json.JSONDecodeError:
            print(body)
except Exception as exc:
    print(f"HTTPS test failed: {exc}")
    print("Start server with: python scripts/https/run_https.py")
