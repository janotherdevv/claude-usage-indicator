import json
import logging
import time
import urllib.request
import urllib.error
from datetime import datetime

from .config import CREDENTIALS_PATH, API_URL
from .history import update_daily_usage

_log = logging.getLogger("claude_usage")


def read_token():
    try:
        with open(CREDENTIALS_PATH) as f:
            creds = json.load(f)
        oauth = creds["claudeAiOauth"]
        expires_at_ms = oauth.get("expiresAt", 0)
        if expires_at_ms and time.time() * 1000 > expires_at_ms:
            return None, "Token expired, reopen Claude Code :)"
        return oauth["accessToken"], None
    except FileNotFoundError:
        return None, f"Credentials not found: {CREDENTIALS_PATH}"
    except (KeyError, json.JSONDecodeError) as e:
        return None, f"Credentials parse error: {e}"


def fetch_usage(token):
    req = urllib.request.Request(
        API_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            five_h = data.get("five_hour", {}).get("utilization", 0)
            seven_d = data.get("seven_day", {}).get("utilization", 0)
            five_h_reset = format_reset_time(data.get("five_hour", {}).get("resets_at", ""))
            seven_d_raw_reset = data.get("seven_day", {}).get("resets_at", "")
            seven_d_reset = format_reset_time(seven_d_raw_reset)
            
            # Registrar uso diario para los indicadores del arco, sincronizando con el ciclo oficial
            update_daily_usage(seven_d, resets_at=seven_d_raw_reset)

            _log.info(
                "Usage fetched | 5h window: %.1f%% (resets: %s) | 7d window: %.1f%% (resets: %s)",
                five_h, five_h_reset, seven_d, seven_d_reset
            )
            return data, None
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        err = f"HTTP {e.code}: {body[:200]}"
        _log.error(err)
        return None, err
    except urllib.error.URLError as e:
        err = f"Network error: {e.reason}"
        _log.error(err)
        return None, err
    except Exception as e:
        err = f"Unexpected error: {e}"
        _log.error(err)
        return None, err


def format_reset_time(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone().strftime("%a %d %b, %H:%M")
    except Exception:
        return iso_str
