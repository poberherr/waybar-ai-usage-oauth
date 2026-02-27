"""Tests for waybar_ai_usage.py setup/cleanup logic."""

from __future__ import annotations

from pathlib import Path

import json5
import pytest

from waybar_ai_usage import (
    TEMPLATE_STYLE,
    _apply_setup,
    _extract_style_region,
    _find_style_region,
    _remove_config,
    _remove_style_blocks,
)


# ---------------------------------------------------------------------------
# _find_style_region: must span both Claude AND Codex blocks
# ---------------------------------------------------------------------------

CLAUDE_ONLY_CSS = """\
/* Claude Code Usage Monitor Styling */
#custom-claude-usage {
  padding: 0 8px;
}

/* Error state (network failures, auth errors, etc.) */
#custom-claude-usage.critical {
  color: #ff5555;
}
""".splitlines()

BOTH_CSS = """\
/* Claude Code Usage Monitor Styling */
#custom-claude-usage {
  padding: 0 8px;
}

/* Error state (network failures, auth errors, etc.) */
#custom-claude-usage.critical {
  color: #ff5555;
}

/* Codex CLI Usage Monitor Styling */
#custom-codex-usage {
  padding: 0 8px;
}

/* Error state (network failures, auth errors, etc.) */
#custom-codex-usage.critical {
  color: #ff5555;
}
""".splitlines()


class TestFindStyleRegion:
    def test_claude_only(self) -> None:
        region = _find_style_region(CLAUDE_ONLY_CSS)
        assert region is not None
        start, end = region
        text = "\n".join(CLAUDE_ONLY_CSS[start:end])
        assert "#custom-claude-usage" in text
        assert "#custom-codex-usage" not in text

    def test_both_modules(self) -> None:
        region = _find_style_region(BOTH_CSS)
        assert region is not None
        start, end = region
        text = "\n".join(BOTH_CSS[start:end])
        assert "#custom-claude-usage" in text
        assert "#custom-codex-usage" in text

    def test_no_match(self) -> None:
        assert _find_style_region(["body { color: red; }"]) is None

    def test_surrounding_css_preserved(self) -> None:
        lines = ["body { color: red; }", ""] + BOTH_CSS + ["", "footer { margin: 0; }"]
        region = _find_style_region(lines)
        assert region is not None
        start, end = region
        assert start == 2  # after "body" and blank line
        remaining = lines[:start] + lines[end:]
        assert any("body" in l for l in remaining)
        assert any("footer" in l for l in remaining)


# ---------------------------------------------------------------------------
# _extract_style_region on the built-in TEMPLATE_STYLE
# ---------------------------------------------------------------------------

class TestExtractTemplateStyle:
    def test_template_contains_both_modules(self) -> None:
        region = _extract_style_region(TEMPLATE_STYLE.splitlines())
        text = "\n".join(region)
        assert "#custom-claude-usage" in text
        assert "#custom-codex-usage" in text


# ---------------------------------------------------------------------------
# _remove_style_blocks: fallback path (no region markers) still catches Codex
# ---------------------------------------------------------------------------

class TestRemoveStyleBlocks:
    def test_fallback_removes_codex(self) -> None:
        """When there's no start marker, the fallback target-matching path
        should still remove #custom-codex-usage blocks."""
        lines = [
            "#custom-codex-usage {",
            "  padding: 0 8px;",
            "}",
        ]
        result = _remove_style_blocks(lines)
        assert not any("#custom-codex-usage" in l for l in result)


# ---------------------------------------------------------------------------
# Round-trip: setup → cleanup leaves files clean
# ---------------------------------------------------------------------------

class TestRoundTrip:
    @pytest.fixture()
    def waybar_dir(self, tmp_path: Path) -> tuple[Path, Path]:
        config = tmp_path / "config.jsonc"
        style = tmp_path / "style.css"
        # Minimal starting config
        config.write_text(json5.dumps({"modules-left": ["clock"]}) + "\n")
        style.write_text("/* user styles */\nbody { color: white; }\n")
        return config, style

    def test_setup_adds_both_modules(self, waybar_dir: tuple[Path, Path]) -> None:
        config, style = waybar_dir
        _apply_setup(config, style, dry_run=False)

        data = json5.loads(config.read_text())
        assert "custom/claude-usage" in data["modules-left"]
        assert "custom/codex-usage" in data["modules-left"]
        assert "custom/claude-usage" in data
        assert "custom/codex-usage" in data

        css = style.read_text()
        assert "#custom-claude-usage" in css
        assert "#custom-codex-usage" in css

    def test_setup_is_idempotent(self, waybar_dir: tuple[Path, Path]) -> None:
        config, style = waybar_dir
        _apply_setup(config, style, dry_run=False)
        first_config = config.read_text()
        first_style = style.read_text()

        _apply_setup(config, style, dry_run=False)
        assert config.read_text() == first_config
        assert style.read_text() == first_style

    def test_cleanup_removes_both_modules(self, waybar_dir: tuple[Path, Path]) -> None:
        config, style = waybar_dir
        _apply_setup(config, style, dry_run=False)
        _remove_config(config, style, dry_run=False)

        data = json5.loads(config.read_text())
        assert "custom/claude-usage" not in data.get("modules-left", [])
        assert "custom/codex-usage" not in data.get("modules-left", [])
        assert "custom/claude-usage" not in data
        assert "custom/codex-usage" not in data

        css = style.read_text()
        assert "#custom-claude-usage" not in css
        assert "#custom-codex-usage" not in css

    def test_cleanup_preserves_existing_content(
        self, waybar_dir: tuple[Path, Path]
    ) -> None:
        config, style = waybar_dir
        _apply_setup(config, style, dry_run=False)
        _remove_config(config, style, dry_run=False)

        data = json5.loads(config.read_text())
        assert "clock" in data["modules-left"]

        css = style.read_text()
        assert "/* user styles */" in css
        assert "body { color: white; }" in css
