#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MANAGE_SCRIPT="$SCRIPT_DIR/manage_managed_bundle_keys.py"

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

keys_path="$tmpdir/trusted-managed-bundle-keys.json"
private_dir="$tmpdir/private"
cp "$REPO_ROOT/keys/trusted-managed-bundle-keys.json" "$keys_path"

python3 "$MANAGE_SCRIPT" validate --keys-path "$keys_path" >/dev/null
python3 "$MANAGE_SCRIPT" list --keys-path "$keys_path" >/dev/null

new_key_id="spidervenoms-rotated-test-2026-04"
new_private_key="$private_dir/${new_key_id}.pem"
python3 "$MANAGE_SCRIPT" rotate \
  --keys-path "$keys_path" \
  --new-key-id "$new_key_id" \
  --private-key-out "$new_private_key" \
  --created-at "2026-04-01T00:00:00Z" \
  --rotates-after "2026-10-01T00:00:00Z" >/dev/null

test -f "$new_private_key"

python3 - "$keys_path" "$new_key_id" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
new_key_id = sys.argv[2]
keys = json.loads(path.read_text())

old_key = keys["spidervenoms-dev-2026-03"]
assert old_key["status"] == "active"
assert old_key["usage"] == "verify_only"
assert old_key["rotates_after"] == "2026-04-01T00:00:00Z"

new_key = keys[new_key_id]
assert new_key["status"] == "active"
assert new_key["usage"] == "sign_and_verify"
assert new_key["bundle_purposes"] == ["managed_local_bundle"]
assert new_key["created_at"] == "2026-04-01T00:00:00Z"
assert new_key["rotates_after"] == "2026-10-01T00:00:00Z"
assert new_key["revoked_at"] is None
assert new_key["revocation_reason"] is None
PY

python3 "$MANAGE_SCRIPT" validate --keys-path "$keys_path" >/dev/null

python3 "$MANAGE_SCRIPT" revoke \
  --keys-path "$keys_path" \
  --key-id "$new_key_id" \
  --reason "workflow fixture revocation" \
  --revoked-at "2026-04-02T00:00:00Z" \
  --allow-no-active-signer >/dev/null

python3 - "$keys_path" "$new_key_id" <<'PY'
import json
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
new_key_id = sys.argv[2]
keys = json.loads(path.read_text())
entry = keys[new_key_id]
assert entry["status"] == "revoked"
assert entry["usage"] == "verify_only"
assert entry["revoked_at"] == "2026-04-02T00:00:00Z"
assert entry["revocation_reason"] == "workflow fixture revocation"
PY

if python3 "$MANAGE_SCRIPT" validate --keys-path "$keys_path" >/dev/null 2>&1; then
  echo "error: key policy unexpectedly validated without an active signer" >&2
  exit 1
fi

python3 "$MANAGE_SCRIPT" validate --keys-path "$keys_path" --allow-no-active-signer >/dev/null

echo "managed bundle key workflow checks ok"
