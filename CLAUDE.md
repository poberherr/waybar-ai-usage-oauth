# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Waybar modules that monitor Claude Code and Codex CLI usage (5h/7d windows) via OAuth credentials. Fork of [NihilDigit/waybar-ai-usage](https://github.com/NihilDigit/waybar-ai-usage) — rewritten to use OAuth tokens instead of browser cookies.

## Architecture

- **`claude.py`** — Claude Code usage monitor. Reads OAuth token from `~/.claude/.credentials.json`, calls `https://api.anthropic.com/api/oauth/usage` with Bearer token + `anthropic-beta: oauth-2025-04-20` header. Outputs CLI or Waybar JSON. Entry point: `claude-usage`.
- **`codex.py`** — Codex CLI usage monitor. Reads OAuth token from `~/.codex/auth.json`, calls `https://chatgpt.com/backend-api/wham/usage`. Handles token refresh via `auth.openai.com/oauth/token`. Outputs CLI or Waybar JSON. Entry point: `codex-usage`.
- **`common.py`** — Shared utilities: file-based caching (`~/.cache/waybar-ai-usage/`), `WindowUsage` dataclass, time formatting, conditional template engine (`format_output` supports `{?var}...{/var}` conditionals).
- **`waybar_ai_usage.py`** — Setup/cleanup/restore helper that patches user's Waybar config.jsonc and style.css (with timestamped `.bak.*` backups). Uses `json-five` for JSONC parsing. Entry point: `waybar-ai-usage`.
- **`pyproject.toml`** — Hatchling build. Wheel includes all four `.py` files.

## Development

```bash
uv sync                          # Install deps
uv run python claude.py          # CLI test (Claude)
uv run python claude.py --waybar # Waybar JSON test (Claude)
uv run python codex.py           # CLI test (Codex)
uv run python codex.py --waybar  # Waybar JSON test (Codex)
uv run python waybar_ai_usage.py setup --dry-run  # Setup dry-run
```

No test suite exists. Manual testing with the above commands.

## Releasing

```bash
./release.sh 0.5.1   # Bumps version, tags, pushes to GitHub + AUR
```

The script updates `pyproject.toml` and `aur/waybar-ai-usage-oauth/PKGBUILD`, creates a git tag, pushes, downloads the tarball to update PKGBUILD checksums, regenerates `.SRCINFO`, and pushes to AUR. See `RELEASING.md` for details.

## Key Details

- **Claude**: OAuth credentials at `~/.claude/.credentials.json` → `claudeAiOauth.accessToken`
  - `expiresAt` is milliseconds since epoch
  - API returns `five_hour` and `seven_day` windows with `utilization` (0-100) and `resets_at` (ISO timestamp)
  - CSS classes: `claude-low`, `claude-mid`, `claude-high`; Waybar signal 8
- **Codex**: OAuth credentials at `~/.codex/auth.json` → `tokens.access_token`
  - Token refresh handled in-app via `auth.openai.com/oauth/token` (client_id `app_EMoamEEZ73f0CkXaXp7hrann`)
  - Refreshes if `last_refresh` > 8 days old, or on 401 response
  - API returns `rate_limit.primary_window` (5h) and `secondary_window` (7d) with `used_percent` and `reset_at` (Unix timestamp)
  - CSS classes: `codex-low`, `codex-mid`, `codex-high`; Waybar signal 9
  - `CODEX_HOME` env var overrides default `~/.codex` path
- Cache TTL is 60s to prevent rate limiting across multi-monitor Waybar instances
- Cache uses file-based locking (`*.updating` marker files) to coordinate between concurrent Waybar processes
- Auto-switches from 5h to 7d display when 7-day usage exceeds 80% (overridden by `--show-5h`)
- Waybar error states show short labels: "Token Exp", "Auth Err", "No Creds", "Net Err"
- Version tracked in `pyproject.toml` and `aur/waybar-ai-usage-oauth/PKGBUILD` — keep in sync

## Dependencies

Runtime: `requests`, `json-five`. Python 3.11+. Build: `hatchling`.
