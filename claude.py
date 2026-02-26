from __future__ import annotations

import argparse
import json
import sys
import time

from pathlib import Path

import requests

from common import format_eta, parse_window_percent, format_output, get_cached_or_fetch


# ==================== Configuration ====================

CREDENTIALS_PATH = Path.home() / ".claude" / ".credentials.json"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

# SVG icon path (unused in current version)
SCRIPT_DIR = Path(__file__).parent
ICON_PATH = SCRIPT_DIR / "assets" / "claude.svg"


# ==================== OAuth Token ====================

def _load_oauth_token() -> str:
    """Load and validate the OAuth access token from Claude Code credentials."""
    if not CREDENTIALS_PATH.exists():
        raise RuntimeError(
            f"Credentials not found: {CREDENTIALS_PATH}\n"
            "Run Claude Code at least once to create OAuth credentials."
        )

    try:
        creds = json.loads(CREDENTIALS_PATH.read_text())
    except Exception as e:
        raise RuntimeError(f"Failed to parse credentials: {e}")

    oauth = creds.get("claudeAiOauth")
    if not oauth:
        raise RuntimeError(
            "No 'claudeAiOauth' entry in credentials.\n"
            "Run Claude Code to set up OAuth authentication."
        )

    token = oauth.get("accessToken")
    if not token:
        raise RuntimeError("Missing accessToken in OAuth credentials.")

    # Check expiry (expiresAt is milliseconds since epoch)
    expires_at = oauth.get("expiresAt")
    if expires_at and time.time() * 1000 > expires_at:
        raise RuntimeError(
            "OAuth token expired.\n"
            "Reopen Claude Code to refresh the token."
        )

    return token


# ==================== Core Logic: Get Usage ====================

def _fetch_claude_usage_uncached() -> dict:
    """Fetch Claude usage data via OAuth token."""
    token = _load_oauth_token()

    headers = {
        "Authorization": f"Bearer {token}",
        "anthropic-beta": "oauth-2025-04-20",
        "Accept": "application/json",
    }

    # Retry once (2 attempts total)
    last_error = None
    for attempt in range(2):
        try:
            resp = requests.get(USAGE_URL, headers=headers, timeout=10)

            if resp.status_code == 401:
                raise RuntimeError(
                    "401 Unauthorized: OAuth token rejected.\n"
                    "Reopen Claude Code to refresh the token."
                )
            if resp.status_code == 403:
                raise RuntimeError("403 Forbidden: Access denied to usage API.")

            resp.raise_for_status()
            return resp.json()

        except requests.RequestException as e:
            last_error = e
            if attempt == 0:
                continue

    raise RuntimeError(f"Request failed: {last_error}")


def get_claude_usage() -> dict:
    """
    Fetch Claude usage data using OAuth token.

    Uses file-based caching to prevent multiple Waybar instances (one per monitor)
    from making concurrent API requests that might be rate-limited.
    """
    return get_cached_or_fetch("claude", _fetch_claude_usage_uncached)


# ==================== Output: CLI / Waybar ====================

def print_cli(usage: dict) -> None:
    """Print usage to terminal (for debugging)."""
    print(json.dumps(usage, indent=2))

    fh = parse_window_percent(usage.get("five_hour"))
    sd = parse_window_percent(usage.get("seven_day"))

    def _fmt_reset(win):
        if win.utilization == 0 and win.resets_at is None:
            return "Not started"
        return format_eta(win.resets_at)

    print("-" * 40)
    print(f"5-hour : {fh.utilization:.1f}%  (Reset in {_fmt_reset(fh)})")
    print(f"7-day  : {sd.utilization:.1f}%  (Reset in {_fmt_reset(sd)})")


def print_waybar(usage: dict, format_str: str | None = None, tooltip_format: str | None = None, show_5h: bool = False) -> None:
    fh = parse_window_percent(usage.get("five_hour"))
    sd = parse_window_percent(usage.get("seven_day"))

    # Get raw window data to check for unused state
    fh_raw = usage.get("five_hour") or {}
    sd_raw = usage.get("seven_day") or {}

    # Prepare all data points without icons
    fh_reset_str = format_eta(fh.resets_at) if fh.resets_at else "Not started"
    sd_reset_str = format_eta(sd.resets_at) if sd.resets_at else "Not started"

    # Icons with colors (users can customize)
    icon_styled = "<span foreground='#DE7356' size='large'>󰜡</span>"
    time_icon_styled = "<span foreground='#DE7356' size='large'>󰔚</span>"

    # Determine active window based on show_5h flag or default logic
    if show_5h:
        # Always show 5-hour window
        target = fh
        target_raw = fh_raw
        win_name = "5h"
        window_length = 18000  # 5 hours in seconds
    elif sd.utilization >= 100:
        # 7-day window exhausted
        target = sd
        target_raw = sd_raw
        win_name = "7d"
        window_length = 604800
    elif sd.utilization > 80:
        # 7-day window high usage
        target = sd
        target_raw = sd_raw
        win_name = "7d"
        window_length = 604800  # 7 days in seconds
    else:
        # Default to 5h window
        target = fh
        target_raw = fh_raw
        win_name = "5h"
        window_length = 18000  # 5 hours in seconds

    pct = int(round(target.utilization))

    window_not_started = (target.utilization == 0 and target.resets_at is None)

    # Check if window is unused (utilization == 0 and reset time near window length)
    is_unused = False
    if target.utilization == 0 and target.resets_at:
        from datetime import datetime, timezone
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

            # If reset time is close to window length (allow 1s error), consider it unused
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
        # Default format (backward compatible)
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
        # Default tooltip
        tooltip = (
            "Window     Used    Reset\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"5-Hour     {fh.utilization:>3.0f}%    {fh_reset_str}\n"
            f"7-Day      {sd.utilization:>3.0f}%    {sd_reset_str}\n"
            "\n"
            "Click to Refresh"
        )

    if pct < 50:
        cls = "claude-low"
    elif pct < 80:
        cls = "claude-mid"
    else:
        cls = "claude-high"

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
        usage = get_claude_usage()
    except Exception as e:
        if args.waybar:
            err_msg = str(e)
            if "expired" in err_msg.lower() or "401" in err_msg:
                short_err = "Token Exp"
            elif "403" in err_msg:
                short_err = "Auth Err"
            elif "not found" in err_msg.lower():
                short_err = "No Creds"
            else:
                short_err = "Net Err"
            print(json.dumps({
                "text": f"<span foreground='#ff5555'>󰜡 {short_err}</span>",
                "tooltip": f"Error fetching Claude usage:\n{err_msg}",
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
