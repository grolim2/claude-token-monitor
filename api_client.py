"""
Fetches real usage from Anthropic OAuth API.
Endpoint: GET https://api.anthropic.com/api/oauth/usage
Auth:     Bearer token from ~/.claude/.credentials.json.
          Token is refreshed by running `claude -p .` as a subprocess, which
          updates the credentials file internally (avoids Cloudflare WAF).
"""

import json
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path

CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"


def _load_creds() -> dict:
    return json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))


def _is_expired(creds: dict) -> bool:
    expires_at = creds.get("claudeAiOauth", {}).get("expiresAt", 0)
    return time.time() * 1000 > expires_at - 60_000


def _refresh_via_cli():
    """Run a no-op claude prompt to force the CLI to refresh its OAuth token.
    Uses shell=True so Windows finds claude.cmd/.ps1 in npm PATH."""
    subprocess.run(
        "claude -p . --output-format json",
        capture_output=True, timeout=30, check=False, shell=True
    )


def _get_access_token() -> str:
    creds = _load_creds()
    if _is_expired(creds):
        _refresh_via_cli()
        creds = _load_creds()
    return creds["claudeAiOauth"]["accessToken"]


def _call_usage(token: str) -> dict:
    req = urllib.request.Request(USAGE_URL)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("anthropic-beta", "oauth-2025-04-20")
    req.add_header("anthropic-version", "2023-06-01")
    req.add_header("User-Agent",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def get_usage() -> dict:
    """
    Returns dict:
      five_hour.utilization  : float (0-100)
      five_hour.resets_at    : str ISO-8601
      seven_day.utilization  : float
      seven_day.resets_at    : str ISO-8601
      error                  : str (on failure)
    """
    try:
        token = _get_access_token()
        result = _call_usage(token)
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        if e.code == 401:
            try:
                _refresh_via_cli()
                token = _load_creds()["claudeAiOauth"]["accessToken"]
                return _call_usage(token)
            except Exception as e2:
                return {"error": f"Auth falhou após refresh: {e2}"}
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}
