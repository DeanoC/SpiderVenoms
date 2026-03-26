#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VERIFY_SCRIPT="$SCRIPT_DIR/managed_bundle_envelope.py"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

bundle_root="$tmpdir/bundle"
keys_path="$tmpdir/trusted-managed-bundle-keys.json"
cp -R "$REPO_ROOT/assets/bundles/managed-local" "$bundle_root"
cp "$REPO_ROOT/keys/trusted-managed-bundle-keys.json" "$keys_path"

release_path="$bundle_root/release.json"

python3 "$VERIFY_SCRIPT" verify --release-path "$release_path" --keys-path "$keys_path" >/dev/null

tampered_release="$tmpdir/tampered-release.json"
cp "$release_path" "$tampered_release"
python3 - "$tampered_release" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text())
data["channel"] = "tampered"
path.write_text(json.dumps(data, indent=2) + "\n")
PY
if python3 "$VERIFY_SCRIPT" verify --release-path "$tampered_release" --keys-path "$keys_path" >/dev/null 2>&1; then
  echo "error: tampered release unexpectedly verified" >&2
  exit 1
fi

revoked_keys_path="$tmpdir/revoked-keys.json"
cp "$keys_path" "$revoked_keys_path"
python3 - "$revoked_keys_path" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text())
data["spidervenoms-dev-2026-03"]["status"] = "revoked"
data["spidervenoms-dev-2026-03"]["usage"] = "verify_only"
data["spidervenoms-dev-2026-03"]["revoked_at"] = "2026-03-26T12:50:00Z"
data["spidervenoms-dev-2026-03"]["revocation_reason"] = "test fixture revocation"
path.write_text(json.dumps(data, indent=2) + "\n")
PY
if python3 "$VERIFY_SCRIPT" verify --release-path "$release_path" --keys-path "$revoked_keys_path" >/dev/null 2>&1; then
  echo "error: revoked key unexpectedly verified" >&2
  exit 1
fi

wrong_purpose_keys_path="$tmpdir/wrong-purpose-keys.json"
cp "$keys_path" "$wrong_purpose_keys_path"
python3 - "$wrong_purpose_keys_path" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text())
data["spidervenoms-dev-2026-03"]["bundle_purposes"] = ["other_bundle"]
path.write_text(json.dumps(data, indent=2) + "\n")
PY
if python3 "$VERIFY_SCRIPT" verify --release-path "$release_path" --keys-path "$wrong_purpose_keys_path" >/dev/null 2>&1; then
  echo "error: wrong-purpose key unexpectedly verified" >&2
  exit 1
fi

sign_forbidden_keys_path="$tmpdir/sign-forbidden-keys.json"
cp "$keys_path" "$sign_forbidden_keys_path"
python3 - "$sign_forbidden_keys_path" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
data = json.loads(path.read_text())
data["spidervenoms-dev-2026-03"]["usage"] = "verify_only"
path.write_text(json.dumps(data, indent=2) + "\n")
PY
if python3 "$VERIFY_SCRIPT" sign --release-path "$release_path" --keys-path "$sign_forbidden_keys_path" --key-id spidervenoms-dev-2026-03 --private-key /dev/null >/dev/null 2>&1; then
  echo "error: verify-only key unexpectedly allowed signing" >&2
  exit 1
fi

echo "managed bundle policy negative checks ok"
