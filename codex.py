from __future__ import annotations

import argparse
import json
import os
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

import requests

from common import format_eta, parse_window_percent, format_output, get_cached_or_fetch


# ==================== Configuration ====================

CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
AUTH_PATH = CODEX_HOME / "auth.json"

USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"
TOKEN_REFRESH_URL = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"

# Refresh if last_refresh is older than 8 days
REFRESH_MAX_AGE_DAYS = 8


# ==================== OAuth Token ====================

def _load_auth() -> dict:
    """Load and validate the auth file from Codex CLI."""
    if not AUTH_PATH.exists():
        raise RuntimeError(
            f"Codex auth not found: {AUTH_PATH}\n"
            "Run `codex --login` to authenticate."
        )

    try:
        auth = json.loads(AUTH_PATH.read_text())
    except Exception as e:
        raise RuntimeError(f"Failed to parse {AUTH_PATH}: {e}")

    # Detect API key mode (not supported — we need OAuth)
    if auth.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "Codex is configured with an API key, not OAuth.\n"
            "Run `codex --login` to switch to OAuth authentication."
        )

    tokens = auth.get("tokens")
    if not tokens or not isinstance(tokens, dict):
        raise RuntimeError(
            f"No 'tokens' entry in {AUTH_PATH}.\n"
            "Run `codex --login` to authenticate."
        )

    if not tokens.get("access_token"):
        raise RuntimeError(
            "Missing access_token in Codex auth.\n"
            "Run `codex --login` to authenticate."
        )

    return auth


def _needs_refresh(auth: dict) -> bool:
    """Check if the token needs refreshing based on last_refresh timestamp."""
    last_refresh = auth.get("last_refresh")
    if not last_refresh:
        return True

    try:
        if isinstance(last_refresh, str):
            if last_refresh.endswith('Z'):
                last_refresh = last_refresh[:-1] + '+00:00'
            refresh_dt = datetime.fromisoformat(last_refresh)
        else:
            refresh_dt = datetime.fromtimestamp(last_refresh, tz=timezone.utc)

        age = datetime.now(timezone.utc) - refresh_dt
        return age.days >= REFRESH_MAX_AGE_DAYS
    except Exception:
        return True


def _refresh_token(auth: dict) -> dict:
    """Refresh the OAuth token and write updated auth back to disk."""
    tokens = auth["tokens"]
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise RuntimeError(
            "No refresh_token in Codex auth — cannot refresh.\n"
            "Run `codex --login` to re-authenticate."
        )

    resp = requests.post(TOKEN_REFRESH_URL, json={
        "client_id": CLIENT_ID,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }, timeout=10)

    if resp.status_code != 200:
        raise RuntimeError(
            f"Token refresh failed ({resp.status_code}).\n"
            "Run `codex --login` to re-authenticate."
        )

    data = resp.json()
    tokens["access_token"] = data["access_token"]
    if "refresh_token" in data:
        tokens["refresh_token"] = data["refresh_token"]
    if "id_token" in data:
        tokens["id_token"] = data["id_token"]

    auth["tokens"] = tokens
    auth["last_refresh"] = datetime.now(timezone.utc).isoformat()

    try:
        AUTH_PATH.write_text(json.dumps(auth, indent=2) + "\n")
    except Exception:
        pass  # Non-fatal — we have the refreshed token in memory

    return auth


def _get_access_token() -> tuple[str, str | None]:
    """
    Get a valid access token, refreshing if needed.

    Returns:
        Tuple of (access_token, account_id).
    """
    auth = _load_auth()

    if _needs_refresh(auth):
        auth = _refresh_token(auth)

    tokens = auth["tokens"]
    return tokens["access_token"], tokens.get("account_id")


# ==================== Core Logic: Get Usage ====================

def _fetch_codex_usage_uncached() -> dict:
    """Fetch Codex usage data via OAuth token."""
    access_token, account_id = _get_access_token()

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    if account_id:
        headers["ChatGPT-Account-Id"] = account_id

    # Retry once (2 attempts total), refresh token on 401
    last_error = None
    for attempt in range(2):
        try:
            resp = requests.get(USAGE_URL, headers=headers, timeout=10)

            if resp.status_code == 401 and attempt == 0:
                # Token may have expired — refresh and retry
                auth = _load_auth()
                auth = _refresh_token(auth)
                tokens = auth["tokens"]
                headers["Authorization"] = f"Bearer {tokens['access_token']}"
                if tokens.get("account_id"):
                    headers["ChatGPT-Account-Id"] = tokens["account_id"]
                continue

            if resp.status_code == 401:
                raise RuntimeError(
                    "401 Unauthorized: Codex token rejected.\n"
                    "Run `codex --login` to re-authenticate."
                )
            if resp.status_code == 403:
                raise RuntimeError("403 Forbidden: Access denied to Codex usage API.")

            resp.raise_for_status()
            return resp.json()

        except requests.RequestException as e:
            last_error = e
            if attempt == 0:
                continue

    raise RuntimeError(f"Request failed: {last_error}")


def get_codex_usage() -> dict:
    """
    Fetch Codex usage data using OAuth token.

    Uses file-based caching to prevent multiple Waybar instances (one per monitor)
    from making concurrent API requests that might be rate-limited.
    """
    return get_cached_or_fetch("codex", _fetch_codex_usage_uncached)


# ==================== Output: CLI / Waybar ====================

def print_cli(usage: dict) -> None:
    """Print usage to terminal (for debugging)."""
    print(json.dumps(usage, indent=2))

    rl = usage.get("rate_limit", {})
    fh = parse_window_percent(rl.get("primary_window"), key="used_percent", reset_key="reset_at")
    sd = parse_window_percent(rl.get("secondary_window"), key="used_percent", reset_key="reset_at")

    def _fmt_reset(win):
        if win.utilization == 0 and win.resets_at is None:
            return "Not started"
        return format_eta(win.resets_at)

    print("-" * 40)
    print(f"5-hour : {fh.utilization:.1f}%  (Reset in {_fmt_reset(fh)})")
    print(f"7-day  : {sd.utilization:.1f}%  (Reset in {_fmt_reset(sd)})")


def print_waybar(usage: dict, format_str: str | None = None, tooltip_format: str | None = None, show_5h: bool = False) -> None:
    rl = usage.get("rate_limit", {})
    fh = parse_window_percent(rl.get("primary_window"), key="used_percent", reset_key="reset_at")
    sd = parse_window_percent(rl.get("secondary_window"), key="used_percent", reset_key="reset_at")

    # Get raw window data to check for unused state
    fh_raw = rl.get("primary_window") or {}
    sd_raw = rl.get("secondary_window") or {}

    # Prepare all data points without icons
    fh_reset_str = format_eta(fh.resets_at) if fh.resets_at else "Not started"
    sd_reset_str = format_eta(sd.resets_at) if sd.resets_at else "Not started"

    # Icons with colors (Codex uses OpenAI green)
    icon_styled = "<span foreground='#10A37F' size='large'>󰜡</span>"
    time_icon_styled = "<span foreground='#10A37F' size='large'>󰔚</span>"

    # Determine active window based on show_5h flag or default logic
    if show_5h:
        target = fh
        target_raw = fh_raw
        win_name = "5h"
        window_length = 18000  # 5 hours in seconds
    elif sd.utilization >= 100:
        target = sd
        target_raw = sd_raw
        win_name = "7d"
        window_length = 604800
    elif sd.utilization > 80:
        target = sd
        target_raw = sd_raw
        win_name = "7d"
        window_length = 604800
    else:
        target = fh
        target_raw = fh_raw
        win_name = "5h"
        window_length = 18000

    pct = int(round(target.utilization))

    window_not_started = (target.utilization == 0 and target.resets_at is None)

    # Check if window is unused (utilization == 0 and reset time near window length)
    is_unused = False
    if target.utilization == 0 and target.resets_at:
        try:
            if isinstance(target.resets_at, str):
                reset_at_str = target.resets_at
                if reset_at_str.endswith('Z'):
                    reset_at_str = reset_at_str[:-1] + '+00:00'
                reset_dt = datetime.fromisoformat(reset_at_str)
            else:
                reset_dt = datetime.fromtimestamp(target.resets_at, tz=timezone.utc)

            now = datetime.now(timezone.utc)
            reset_after = int((reset_dt - now).total_seconds())

            is_unused = (reset_after >= window_length - 1)
        except Exception:
            pass

    # Determine status
    if sd.utilization >= 100:
        status = "Pause"
    elif is_unused or window_not_started:
        status = "Ready"
    else:
        status = ""

    # Prepare data dictionary for formatting
    data = {
        "5h_pct": int(round(fh.utilization)),
        "7d_pct": int(round(sd.utilization)),
        "5h_reset": fh_reset_str,
        "7d_reset": sd_reset_str,
        "icon": icon_styled,
        "icon_plain": "󰜡",
        "time_icon": time_icon_styled,
        "time_icon_plain": "󰔚",
        "status": status,
        "pct": pct,
        "reset": format_eta(target.resets_at) if target.resets_at else "Not started",
        "win": win_name,
    }

    # Use custom format or default
    if format_str:
        text = format_output(format_str, data)
    else:
        if status == "Pause":
            text = f"{icon_styled} Pause"
        elif status == "Ready":
            text = f"{icon_styled} Ready"
        else:
            text = f"{icon_styled} {pct}% {time_icon_styled} {data['reset']}"

    # Use custom tooltip format or default
    if tooltip_format:
        tooltip = format_output(tooltip_format, data)
    else:
        tooltip = (
            "Window     Used    Reset\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"5-Hour     {fh.utilization:>3.0f}%    {fh_reset_str}\n"
            f"7-Day      {sd.utilization:>3.0f}%    {sd_reset_str}\n"
            "\n"
            "Click to Refresh"
        )

    if pct < 50:
        cls = "codex-low"
    elif pct < 80:
        cls = "codex-mid"
    else:
        cls = "codex-high"

    output = {
        "text": text,
        "tooltip": tooltip,
        "class": cls,
        "alt": win_name,
        "percentage": data["5h_pct"] if show_5h else data["pct"],
    }

    print(json.dumps(output))


# ==================== CLI Entry Point ====================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--waybar",
        action="store_true",
        help="Output in JSON format for Waybar custom module",
    )
    parser.add_argument(
        "--format",
        type=str,
        help=(
            "Custom format string for waybar text. Available: {icon}, {icon_plain}, "
            "{time_icon}, {time_icon_plain}, {5h_pct}, {7d_pct}, {5h_reset}, {7d_reset}, "
            "{status}, {pct}, {reset}, {win}. Example: '{icon_plain} {5h_pct}%%'"
        ),
    )
    parser.add_argument(
        "--tooltip-format",
        type=str,
        help="Custom format string for tooltip. Uses same variables as --format.",
    )
    parser.add_argument(
        "--show-5h",
        action="store_true",
        help="Always show 5-hour window data (instead of auto-switching to 7-day at 80%%)",
    )
    args = parser.parse_args()

    try:
        usage = get_codex_usage()
    except Exception as e:
        if args.waybar:
            err_msg = str(e)
            if "expired" in err_msg.lower() or "401" in err_msg:
                short_err = "Token Exp"
            elif "403" in err_msg:
                short_err = "Auth Err"
            elif "not found" in err_msg.lower():
                short_err = "No Creds"
            elif "refresh" in err_msg.lower():
                short_err = "Refresh Err"
            else:
                short_err = "Net Err"
            print(json.dumps({
                "text": f"<span foreground='#ff5555'>󰜡 {short_err}</span>",
                "tooltip": f"Error fetching Codex usage:\n{err_msg}",
                "class": "critical"
            }))
            sys.exit(0)
        else:
            print(f"[!] Critical Error: {e}", file=sys.stderr)
            sys.exit(1)

    if args.waybar:
        print_waybar(usage, args.format, args.tooltip_format, args.show_5h)
    else:
        print_cli(usage)


if __name__ == "__main__":
    main()
