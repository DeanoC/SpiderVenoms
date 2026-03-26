#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SPIDERWEB_REPO_DIR="${SPIDERWEB_REPO_DIR:-$REPO_ROOT/../Spiderweb}"
VERSION_DEFAULT="$(sed -n 's/.*\.version = "\(.*\)",/\1/p' "$REPO_ROOT/build.zig.zon" | head -n1)"
OUT_DIR_DEFAULT="$REPO_ROOT/dist"

usage() {
  cat <<'EOF'
Build a macOS SpiderVenoms release archive containing the installed managed bundle artifacts.

Usage:
  package-spidervenoms-macos-release.sh [--version <version>] [--out-dir <dir>]

Outputs:
  <out-dir>/spidervenoms-managed-local-macos-<arch>.tar.gz
  <out-dir>/spidervenoms-managed-local-macos-<arch>.tar.gz.sha256
EOF
}

fail() {
  echo "error: $*" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "missing required command: $1"
}

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) ARCH_LABEL="x86_64" ;;
  arm64|aarch64) ARCH_LABEL="arm64" ;;
  *) ARCH_LABEL="$ARCH" ;;
esac

VERSION="$VERSION_DEFAULT"
OUT_DIR="$OUT_DIR_DEFAULT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      [[ $# -ge 2 ]] || fail "--version requires a value"
      VERSION="$2"
      shift 2
      ;;
    --out-dir)
      [[ $# -ge 2 ]] || fail "--out-dir requires a value"
      OUT_DIR="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail "unknown argument: $1"
      ;;
  esac
done

require_command zig
require_command tar
require_command shasum
[[ -f "$SPIDERWEB_REPO_DIR/build.zig" ]] || fail "Spiderweb checkout not found at $SPIDERWEB_REPO_DIR"
[[ -d "$SPIDERWEB_REPO_DIR/deps/spider-node" ]] || fail "Spiderweb dependencies not found under $SPIDERWEB_REPO_DIR/deps"

WORK_ROOT="$(mktemp -d)"
trap 'rm -rf "$WORK_ROOT"' EXIT

BUILD_PREFIX="$WORK_ROOT/prefix"
ARCHIVE_ROOT="$WORK_ROOT/archive-root"
ARCHIVE_BASENAME="spidervenoms-managed-local-macos-${ARCH_LABEL}"
ARCHIVE_PATH="$OUT_DIR/${ARCHIVE_BASENAME}.tar.gz"
SHA_PATH="${ARCHIVE_PATH}.sha256"

mkdir -p "$BUILD_PREFIX" "$ARCHIVE_ROOT" "$OUT_DIR"

echo "==> Validating version sync"
(
  cd "$REPO_ROOT"
  ./scripts/check-version-sync.sh
)

echo "==> Building SpiderVenoms install prefix"
(
  cd "$REPO_ROOT"
  zig build install --release=safe --prefix "$BUILD_PREFIX"
)

[[ -x "$BUILD_PREFIX/bin/spiderweb-local-service" ]] || fail "missing spiderweb-local-service binary"
[[ -f "$BUILD_PREFIX/share/spidervenoms/bundles/managed-local/release.json" ]] || fail "missing managed-local release.json"
[[ -d "$BUILD_PREFIX/share/spidervenoms/bundles/managed-local/manifests" ]] || fail "missing managed-local manifests"

PACKAGE_ROOT="$ARCHIVE_ROOT/$ARCHIVE_BASENAME"
mkdir -p "$PACKAGE_ROOT"
cp -R "$BUILD_PREFIX/bin" "$PACKAGE_ROOT/bin"
cp -R "$BUILD_PREFIX/share" "$PACKAGE_ROOT/share"

echo "==> Writing release archive"
rm -f "$ARCHIVE_PATH" "$SHA_PATH"
tar -C "$ARCHIVE_ROOT" -czf "$ARCHIVE_PATH" "$ARCHIVE_BASENAME"
(cd "$OUT_DIR" && shasum -a 256 "$(basename "$ARCHIVE_PATH")" >"$(basename "$SHA_PATH")")

echo "Archive: $ARCHIVE_PATH"
echo "SHA256:  $SHA_PATH"
echo "Version: $VERSION"
