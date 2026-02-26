# Waybar AI Usage

Monitor **Claude Code** usage directly in your Waybar status bar.

![showcase](https://github.com/user-attachments/assets/13e8a4a1-6778-484f-8a37-cba238aefea5)

This tool displays your Claude Code usage limits in real-time using OAuth credentials from Claude Code — no browser cookies or API keys needed.

## What This Monitors

- **Claude Code**: Claude's AI-powered code editor
  - 5-hour usage window
  - 7-day usage window

## Features

- Real-time usage percentage display
- Countdown timer until quota reset
- Color-coded warnings (green → yellow → red)
- Click to refresh instantly
- Uses Claude Code OAuth credentials — no browser cookies needed
- Special states: "Ready" (unused) and "Pause" (quota exhausted)
- Auto-retry on network errors

## Prerequisites

- **Claude Code** must have been run at least once (creates OAuth credentials at `~/.claude/.credentials.json`)
- **Python 3.11+**
- **uv** package manager ([installation guide](https://docs.astral.sh/uv/getting-started/installation/))

## Installation

### Method 0: AUR (Recommended on Arch)

```bash
yay -S waybar-ai-usage
```

### Method 1: Using uv tool

```bash
# Install from GitHub
uv tool install git+https://github.com/NihilDigit/waybar-ai-usage

# Or install locally for development
git clone https://github.com/NihilDigit/waybar-ai-usage
cd waybar-ai-usage
uv build
uv tool install --force dist/waybar_ai_usage-*-py3-none-any.whl
```

### Method 2: Development Mode

```bash
git clone https://github.com/NihilDigit/waybar-ai-usage
cd waybar-ai-usage
uv sync
```

## Usage

### Command Line

After `uv tool install`:
```bash
# Setup helper (adds modules/styles with backups + confirmation)
waybar-ai-usage setup

# Cleanup helper (removes modules/styles with backups + confirmation)
waybar-ai-usage cleanup

# Restore latest backups (or pass specific backup paths)
waybar-ai-usage restore

# Preview changes without writing
waybar-ai-usage setup --dry-run
waybar-ai-usage cleanup --dry-run
waybar-ai-usage restore --dry-run

# Skip confirmation
waybar-ai-usage setup --yes
waybar-ai-usage cleanup --yes

# Claude usage (CLI output)
claude-usage

# Waybar JSON output
claude-usage --waybar
```

> Note: `setup`/`cleanup` will rewrite your Waybar config JSONC and may change formatting or remove comments. Backups are created before any write.

In development mode:
```bash
uv run python claude.py
```

### Waybar Integration

#### Step 1: Install the tool

```bash
uv tool install waybar-ai-usage
```

After installation, the command `claude-usage` will be available in your PATH.

#### Step 2: Run setup

```bash
waybar-ai-usage setup
```

This will add the required Waybar modules and styles (with backup + confirmation).

#### Step 3: Restart Waybar

```bash
pkill waybar && waybar &
```

**Important Notes**:

- **Use full path `~/.local/bin/`** to ensure modules work when Waybar is
  launched by systemd (auto-start on login). Without the full path, modules will
  only work when Waybar is manually started from a terminal.

## Formatting Configuration

You can customize the output format using the `--format` and `--tooltip-format`
options. This allows you to:

- Show specific data points (5-hour or 7-day)
- Remove or customize icons
- Create your own layout

### Available Variables

All variables are available for both `--format` and `--tooltip-format`:

| Variable            | Description                     | Example                               |
| ------------------- | ------------------------------- | ------------------------------------- |
| `{icon}`            | Service icon with color styling | `<span foreground='#DE7356'>󰜡</span>` |
| `{icon_plain}`      | Service icon without styling    | `󰜡`                                   |
| `{time_icon}`       | Time icon with color styling    | `<span foreground='#DE7356'>󰔚</span>` |
| `{time_icon_plain}` | Time icon without styling       | `󰔚`                                   |
| `{5h_pct}`          | 5-hour window percentage        | `45`                                  |
| `{7d_pct}`          | 7-day window percentage         | `67`                                  |
| `{5h_reset}`        | 5-hour reset time               | `4h23m`                               |
| `{7d_reset}`        | 7-day reset time                | `2d15h`                               |
| `{pct}`             | Active window percentage        | Varies based on active window         |
| `{reset}`           | Active window reset time        | Varies based on active window         |
| `{status}`          | Status text                     | `Ready`, `Pause`, or empty            |
| `{win}`             | Active window name              | `5h` or `7d`                          |

### Format Examples

```bash
# Show only 5-hour data without styled icons
claude-usage --waybar --format "{icon_plain} {5h_pct}% {time_icon_plain} {5h_reset}"

# Show both 5-hour and 7-day percentages
claude-usage --waybar --format "{icon} 5h:{5h_pct}% 7d:{7d_pct}%"

# Minimal format with just percentage
claude-usage --waybar --format "{5h_pct}%"

# Custom tooltip showing both windows
claude-usage --waybar --tooltip-format "5-Hour: {5h_pct}%  Reset: {5h_reset}\n7-Day: {7d_pct}%  Reset: {7d_reset}"

# Always show 5-hour window (disable auto-switch to 7-day)
claude-usage --waybar --show-5h
```

### Waybar Configuration Example

Pass formatting directly to the script using `--format` (useful for styled icons with colors):

```jsonc
"custom/claude-usage": {
    "exec": "~/.local/bin/claude-usage --waybar --format '{icon} {5h_pct}% {time_icon} {5h_reset}'",
    "return-type": "json",
    "interval": 120,
    "on-click": "~/.local/bin/claude-usage --waybar --format '{icon} {5h_pct}% {time_icon} {5h_reset}'"
}
```

When using `--format`, `{icon}` includes HTML color styling.

Without `--format`, the script provides a default formatted text:

```jsonc
"custom/claude-usage": {
    "exec": "~/.local/bin/claude-usage --waybar",
    "return-type": "json",
    "interval": 120
}
```

This displays: `󰜡 98% 󰔚 2d21h` (with colored icons)

**Note**: When using `%` in shell commands, you may need to escape it as `%%`
depending on your shell.

### Conditional Formatting

You can use conditional blocks to show or hide sections based on whether a time
window has started:

**Single variable conditions:**

- `{?5h_reset}...{/5h_reset}` - Show content only if 5h window has started
- `{?7d_reset}...{/7d_reset}` - Show content only if 7d window has started

**Multiple variable conditions:**

- `{?5h_reset&7d_reset}...{/}` - Show content only if both windows have started

#### Conditional Examples

```bash
# Show both windows only if they've started, with separator only when both present
claude-usage --waybar --format '{?5h_reset}{5h_pct}/{5h_reset}{/5h_reset}{?5h_reset&7d_reset} - {/}{?7d_reset}{7d_pct}/{7d_reset}{/7d_reset}'

# Show 5h data only when active, otherwise show nothing
claude-usage --waybar --format '{?5h_reset}{icon} {5h_pct}% {time_icon} {5h_reset}{/5h_reset}'
```

The first example will display:

- Nothing when both windows are "Not started"
- `45/4h23m` when only 5h window is active
- `67/2d15h` when only 7d window is active
- `45/4h23m - 67/2d15h` when both windows are active

## Display States

### Normal States

- **Green** (0-49%): Low usage, plenty of quota remaining
- **Yellow** (50-79%): Moderate usage, consider managing requests
- **Red** (80-99%): High usage, approaching limit

### Special States

- **Ready** (󰜡): Window hasn't been activated yet (0% usage, ~5h remaining)
- **Pause** (󰜡): Weekly quota exhausted (100% usage)

## How It Works

1. **OAuth Token**: Reads the OAuth access token from Claude Code's credentials (`~/.claude/.credentials.json`)
2. **API Request**: Makes an authenticated request to Anthropic's usage API
3. **Usage Parsing**: Extracts usage percentages and reset times from API responses
4. **Waybar Output**: Formats data as JSON for Waybar's custom module
5. **Auto-refresh**: Waybar polls every 2 minutes (configurable via `interval`)

### Network Configuration

- **Timeout**: 10 seconds per request
- **Retry**: 1 automatic retry on failure (total 2 attempts)
- **Refresh interval**: 120 seconds (2 minutes) recommended

## Troubleshooting

### "No Creds" or "Token Exp" Error

- Ensure Claude Code has been run at least once to create OAuth credentials
- If the token has expired, reopen Claude Code to refresh it
- Check that `~/.claude/.credentials.json` exists and contains `claudeAiOauth`

### "Auth Err" (403/401)

- Your OAuth token may have been revoked — reopen Claude Code
- Check if your subscription is still active

### "Net Err"

- Check your internet connection
- The usage API may be temporarily unavailable
- The tool has built-in retry (1 retry with 10s timeout)

## Project Structure

```
waybar-ai-usage/
├── common.py                     # Shared utilities (caching, time formatting, output)
├── claude.py                     # Claude Code usage monitor (OAuth-based)
├── pyproject.toml                # Project metadata and dependencies
├── waybar_ai_usage.py            # Setup/cleanup helper tool
├── waybar-config-example.jsonc   # Template used by setup
├── waybar-style-example.css      # Template used by setup
├── LICENSE                       # MIT License
└── README.md                     # This file
```

## Contributing

Contributions are welcome! Areas for improvement:

- [x] Caching mechanism to reduce API calls
- [x] OAuth-based authentication (no browser cookies)
- [ ] Better error messages
- [ ] More examples and screenshots

### For Maintainers

See [RELEASING.md](RELEASING.md) for release process documentation.

Quick release:
```bash
./release.sh 0.5.0
```

## License

MIT - See [LICENSE](LICENSE) file for details.

## Acknowledgments

- Originally based on [NihilDigit/waybar-ai-usage](https://github.com/NihilDigit/waybar-ai-usage)
- Uses Claude Code OAuth credentials for reliable, cookie-free authentication
