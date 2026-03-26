#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

version="$(sed -n 's/.*\.version = "\(.*\)",/\1/p' "$REPO_ROOT/build.zig.zon" | head -n1)"
[[ -n "$version" ]] || {
  echo "error: could not read version from build.zig.zon" >&2
  exit 1
}

first_changelog_version="$(sed -n 's/^## \([0-9][0-9.]*\) -.*/\1/p' "$REPO_ROOT/CHANGELOG.md" | head -n1)"
if [[ "$first_changelog_version" != "$version" ]]; then
  echo "error: top changelog version does not match build.zig.zon" >&2
  echo "expected: $version" >&2
  echo "actual: ${first_changelog_version:-<missing>}" >&2
  exit 1
fi

python3 - "$REPO_ROOT" "$version" <<'PY'
import json
import pathlib
import sys

repo = pathlib.Path(sys.argv[1])
version = sys.argv[2]

release_path = repo / "assets" / "bundles" / "managed-local" / "release.json"
release = json.loads(release_path.read_text())

def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(1)

if release.get("release_version") != version:
    fail(f"{release_path} release_version does not match {version}")
if release.get("version") != version:
    fail(f"{release_path} version does not match {version}")
if version not in release.get("digest", ""):
    fail(f"{release_path} digest does not include {version}")
signature_value = ((release.get("signature") or {}).get("value")) or ""
if version not in signature_value:
    fail(f"{release_path} signature value does not include {version}")

for package in release.get("packages", []):
    package_id = package.get("package_id", "<unknown>")
    if package.get("release_version") != version:
        fail(f"package {package_id} release_version does not match {version}")
    if package.get("version") != version:
        fail(f"package {package_id} version does not match {version}")
    if version not in (package.get("digest") or ""):
        fail(f"package {package_id} digest does not include {version}")
    package_signature = ((package.get("signature") or {}).get("value")) or ""
    if version not in package_signature:
        fail(f"package {package_id} signature value does not include {version}")

manifests_dir = repo / "assets" / "bundles" / "managed-local" / "manifests"
manifest_paths = sorted(manifests_dir.glob("*.json"))
if not manifest_paths:
    fail(f"no manifests found in {manifests_dir}")

for manifest_path in manifest_paths:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("release_version") != version:
        fail(f"{manifest_path} release_version does not match {version}")
    if version not in (manifest.get("digest") or ""):
        fail(f"{manifest_path} digest does not include {version}")
    manifest_signature = ((manifest.get("signature") or {}).get("value")) or ""
    if version not in manifest_signature:
        fail(f"{manifest_path} signature value does not include {version}")

print(f"version sync ok: {version}")
PY
