#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

skip_bundle_signature=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-bundle-signature)
      skip_bundle_signature=1
      shift
      ;;
    --help|-h)
      cat <<'EOF'
Usage:
  check-version-sync.sh [--skip-bundle-signature]

Checks that the canonical SpiderVenoms version touchpoints remain aligned.
EOF
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

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
if not str(release.get("digest", "")).startswith("sha256:"):
    fail(f"{release_path} digest must use sha256:")

for package in release.get("packages", []):
    package_id = package.get("package_id", "<unknown>")
    if package.get("release_version") != version:
        fail(f"package {package_id} release_version does not match {version}")
    if package.get("version") != version:
        fail(f"package {package_id} version does not match {version}")
    if not str(package.get("digest") or "").startswith("sha256:"):
        fail(f"package {package_id} digest must use sha256:")

manifests_dir = repo / "assets" / "bundles" / "managed-local" / "manifests"
manifest_paths = sorted(manifests_dir.glob("*.json"))
if not manifest_paths:
    fail(f"no manifests found in {manifests_dir}")

for manifest_path in manifest_paths:
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("release_version") != version:
        fail(f"{manifest_path} release_version does not match {version}")
    if not str(manifest.get("digest") or "").startswith("sha256:"):
        fail(f"{manifest_path} digest must use sha256:")

print(f"version sync ok: {version}")
PY

if [[ "$skip_bundle_signature" != "1" ]]; then
  python3 "$SCRIPT_DIR/manage_managed_bundle_keys.py" validate
  python3 "$SCRIPT_DIR/managed_bundle_envelope.py" verify
fi
