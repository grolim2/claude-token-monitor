"""
Fetches real usage data from claude.ai using stored OAuth credentials.
Endpoint: GET https://claude.ai/api/organizations/{org_id}/usage
"""

import json
import urllib.request
import urllib.error
from pathlib import Path

CREDENTIALS_FILE = Path.home() / ".claude" / ".credentials.json"
BASE_URL = "https://claude.ai/api"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/137.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Referer": "https://claude.ai/",
    "Origin": "https://claude.ai",
    "Content-Type": "application/json",
}


def _load_credentials() -> dict:
    data = json.loads(CREDENTIALS_FILE.read_text(encoding="utf-8"))
    oauth = data.get("claudeAiOauth", {})
    return {
        "accessToken": oauth.get("accessToken", ""),
        "subscriptionType": oauth.get("subscriptionType", ""),
    }


def _request(path: str, token: str) -> dict:
    url = BASE_URL + path
    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    # Try both Bearer and Cookie auth
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Cookie", f"sessionKey={token}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def get_usage() -> dict:
    """
    Returns dict with keys (best-effort, structure varies):
      utilization_pct   : float
      reset_at          : str (ISO-8601)
      weekly_pct        : float
      error             : str (on failure)
    """
    try:
        creds = _load_credentials()
        token = creds["accessToken"]
        if not token:
            return {"error": "Token não encontrado em ~/.claude/.credentials.json"}

        # 1. Get org list
        orgs_resp = _request("/organizations", token)
        if isinstance(orgs_resp, list):
            orgs = orgs_resp
        elif isinstance(orgs_resp, dict) and "organizations" in orgs_resp:
            orgs = orgs_resp["organizations"]
        else:
            orgs = [orgs_resp]

        if not orgs:
            return {"error": "Nenhuma organização encontrada"}

        org_id = orgs[0].get("uuid") or orgs[0].get("id") or orgs[0].get("org_id")
        if not org_id:
            return {"error": f"org_id não encontrado. Resposta: {str(orgs)[:200]}"}

        # 2. Get usage
        usage_resp = _request(f"/organizations/{org_id}/usage", token)
        return usage_resp

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        return {"error": f"HTTP {e.code}: {body}"}
    except Exception as e:
        return {"error": str(e)}
