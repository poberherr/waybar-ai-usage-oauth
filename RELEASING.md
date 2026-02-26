# Release Process

This project uses an automated script to simplify the release process, publishing to both GitHub and AUR with a single command.

## Prerequisites

1. **Clean working directory**: All changes committed
2. **On main branch**: Ensure you're on the correct branch
3. **SSH keys**: AUR SSH access configured
4. **makepkg tool**: Required for generating .SRCINFO

## Quick Release

```bash
./release.sh <new-version>
```

Example:
```bash
./release.sh 0.4.1
```

## Detailed Release Steps

The script automatically executes the following steps:

### 1. Version Number Update
- Update version in `pyproject.toml`
- Update version in `aur/waybar-ai-usage-oauth/PKGBUILD`
- Reset `pkgrel` to 1

### 2. Create Git Commit and Tag
- Commit version update: `chore: bump version to X.Y.Z`
- Create tag: `vX.Y.Z`

### 3. Push to GitHub
- Push main branch
- Push tags
- Trigger GitHub Release (if configured)

### 4. Update PKGBUILD Checksum
- Download tarball from GitHub
- Calculate SHA256 checksum
- Update `sha256sums` in PKGBUILD
- Regenerate `.SRCINFO`

### 5. Commit AUR Package Update
- Commit PKGBUILD and .SRCINFO changes
- Push to GitHub main repository

### 6. Push to AUR
- Clone AUR repository to temporary directory
- Copy updated files
- Commit and push to AUR

### 7. Complete
- Display GitHub Release link
- Display AUR package link

## Script Features

### ✅ Safety Checks
- Validate version number format (semantic versioning)
- Check if working directory is clean
- Verify current branch
- Require user confirmation before release

### 🎨 User-Friendly Output
- Colored logs (INFO/SUCCESS/WARN/ERROR)
- Display progress for each step
- Auto-stop on error (set -e)

### 🔄 Automation
- Auto-calculate checksums
- Auto-generate .SRCINFO
- Auto-cleanup temporary files
- Handle Git operations

## Manual Release (Not Recommended)

If manual release is needed, follow these steps:

```bash
# 1. Update version numbers
vim pyproject.toml  # Modify version field
vim aur/waybar-ai-usage-oauth/PKGBUILD  # Modify pkgver field

# 2. Commit and create tag
git add pyproject.toml aur/waybar-ai-usage-oauth/PKGBUILD
git commit -m "chore: bump version to X.Y.Z"
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin main --tags

# 3. Wait for GitHub to process, then update checksum
curl -L "https://api.github.com/repos/poberherr/waybar-ai-usage-oauth/tarball/refs/tags/vX.Y.Z" \
  -o /tmp/waybar-ai-usage-oauth-X.Y.Z.tar.gz
sha256sum /tmp/waybar-ai-usage-oauth-X.Y.Z.tar.gz
# Manually update sha256sums in PKGBUILD

# 4. Generate .SRCINFO
cd aur/waybar-ai-usage-oauth
makepkg --printsrcinfo > .SRCINFO

# 5. Commit AUR update
git add PKGBUILD .SRCINFO
git commit -m "chore: update AUR package to X.Y.Z"
git push

# 6. Push to AUR
cd /tmp
git clone ssh://aur@aur.archlinux.org/waybar-ai-usage-oauth.git
cp ~/path/to/PKGBUILD ~/path/to/.SRCINFO waybar-ai-usage-oauth/
cd waybar-ai-usage-oauth
git add PKGBUILD .SRCINFO
git commit -m "Update to X.Y.Z"
git push
```

## Rollback Release

If a release has issues and needs to be rolled back:

```bash
# Delete local tag
git tag -d vX.Y.Z

# Delete remote tag
git push origin :refs/tags/vX.Y.Z

# Revert commit (if not yet pushed)
git reset --hard HEAD~1

# If already pushed to GitHub, need force push (use with caution)
git push origin main --force

# AUR cannot be rolled back, must publish new version to fix
```

## Common Issues

### Q: Script failed halfway, what should I do?

A: Check the error message, fix the issue, then continue from the failed step:
- If failed before pushing to GitHub: Delete tag and rerun
- If failed before pushing to AUR: Manually complete remaining steps

### Q: Checksum calculation failed?

A: Ensure:
1. GitHub tag is created and accessible
2. Network connection is working
3. Wait enough time for GitHub to process the tag

### Q: AUR push rejected?

A: Check:
1. SSH keys are correctly configured
2. You have maintainer permissions for the AUR package
3. PKGBUILD syntax is correct (test with `makepkg`)

## Version Numbering

This project follows [Semantic Versioning](https://semver.org/):

- **Major version**: Incompatible API changes
- **Minor version**: Backwards-compatible functionality additions
- **Patch version**: Backwards-compatible bug fixes

Examples:
- `0.4.0` → `0.4.1`: Bug fix
- `0.4.1` → `0.5.0`: New feature
- `0.5.0` → `1.0.0`: Major update or API change
