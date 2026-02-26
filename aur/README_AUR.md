# AUR Packaging Notes

## Package

- `waybar-ai-usage-oauth` — OAuth-based fork of waybar-ai-usage

## Dependencies

- `python-requests` (official repos)
- `python-json-five` (AUR)

## Build / Update

1) Update versions and checksums in `waybar-ai-usage-oauth/PKGBUILD`.
2) Generate `.SRCINFO`:
   ```bash
   cd aur/waybar-ai-usage-oauth && makepkg --printsrcinfo > .SRCINFO
   ```
3) Push to AUR, or use `./release.sh <version>` to automate the full release.

## GitHub Source

- https://github.com/poberherr/waybar-ai-usage-oauth

## Notes

- `conflicts=('waybar-ai-usage')` and `provides=('waybar-ai-usage')` allow clean switching from the original package.
- `setup`/`cleanup` rewrite `config.jsonc` (formatting/comments may change); backups are created.
- The AUR package shows a reminder in install/remove hooks to run `waybar-ai-usage cleanup` before uninstall.
