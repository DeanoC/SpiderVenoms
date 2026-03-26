#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import datetime as dt
import pathlib
import stat
import subprocess
from typing import Any

from managed_bundle_envelope import (
    DEFAULT_KEYS_PATH,
    MANAGED_BUNDLE_PURPOSE,
    REPO_ROOT,
    SIGNATURE_SCHEME,
    fail,
    load_json,
    resolve_openssl,
    write_json,
)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        fail(f"{label}: expected non-empty timestamp")
    raw = value.strip()
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        fail(f"{label}: invalid ISO-8601 timestamp: {raw!r} ({exc})")
    if parsed.tzinfo is None:
        fail(f"{label}: timestamp must include timezone information")
    return raw


def validate_public_key_hex(value: Any, label: str) -> str:
    if not isinstance(value, str):
        fail(f"{label}: expected hex string")
    try:
        raw = bytes.fromhex(value)
    except ValueError as exc:
        fail(f"{label}: invalid hex public key ({exc})")
    if len(raw) != 32:
        fail(f"{label}: expected 32-byte Ed25519 public key")
    return value


def load_keys_dict(keys_path: pathlib.Path) -> dict[str, dict[str, Any]]:
    keys = load_json(keys_path)
    if not isinstance(keys, dict):
        fail(f"{keys_path}: trusted key store must be a JSON object")
    if not keys:
        fail(f"{keys_path}: trusted key store is empty")
    normalized: dict[str, dict[str, Any]] = {}
    for key_id, value in keys.items():
        if not isinstance(key_id, str) or not key_id:
            fail(f"{keys_path}: key ids must be non-empty strings")
        if not isinstance(value, dict):
            fail(f"{keys_path}: key {key_id} must map to an object")
        normalized[key_id] = value
    return normalized


def active_signers_for_purpose(keys: dict[str, dict[str, Any]], bundle_purpose: str) -> list[str]:
    signers: list[str] = []
    for key_id, entry in keys.items():
        if entry.get("status") != "active":
            continue
        if entry.get("usage") != "sign_and_verify":
            continue
        purposes = entry.get("bundle_purposes")
        if isinstance(purposes, list) and bundle_purpose in purposes:
            signers.append(key_id)
    return sorted(signers)


def validate_keys(keys: dict[str, dict[str, Any]], *, allow_no_active_signer: bool = False) -> None:
    tracked_purposes: set[str] = set()
    active_signers: dict[str, list[str]] = {}

    for key_id, entry in keys.items():
        publisher = entry.get("publisher")
        if publisher != "SpiderVenoms":
            fail(f"{key_id}: publisher must be 'SpiderVenoms'")

        scheme = entry.get("scheme")
        if scheme != SIGNATURE_SCHEME:
            fail(f"{key_id}: scheme must be {SIGNATURE_SCHEME!r}")

        validate_public_key_hex(entry.get("public_key_hex"), f"{key_id}.public_key_hex")

        status = entry.get("status")
        if status not in {"active", "revoked"}:
            fail(f"{key_id}: status must be 'active' or 'revoked'")

        usage = entry.get("usage")
        if usage not in {"sign_and_verify", "verify_only"}:
            fail(f"{key_id}: usage must be 'sign_and_verify' or 'verify_only'")

        purposes = entry.get("bundle_purposes")
        if not isinstance(purposes, list) or not purposes:
            fail(f"{key_id}: bundle_purposes must be a non-empty array")
        normalized_purposes: list[str] = []
        for purpose in purposes:
            if not isinstance(purpose, str) or not purpose.strip():
                fail(f"{key_id}: bundle purpose entries must be non-empty strings")
            if purpose not in normalized_purposes:
                normalized_purposes.append(purpose)
        tracked_purposes.update(normalized_purposes)

        parse_iso_timestamp(entry.get("created_at"), f"{key_id}.created_at")

        rotates_after = entry.get("rotates_after")
        if rotates_after is not None:
            parse_iso_timestamp(rotates_after, f"{key_id}.rotates_after")

        revoked_at = entry.get("revoked_at")
        revocation_reason = entry.get("revocation_reason")
        if status == "revoked":
            if usage != "verify_only":
                fail(f"{key_id}: revoked keys must use verify_only")
            parse_iso_timestamp(revoked_at, f"{key_id}.revoked_at")
            if not isinstance(revocation_reason, str) or not revocation_reason.strip():
                fail(f"{key_id}: revoked keys must include a revocation_reason")
        else:
            if revoked_at is not None:
                fail(f"{key_id}: active keys must not set revoked_at")
            if revocation_reason is not None:
                fail(f"{key_id}: active keys must not set revocation_reason")

        if status == "active" and usage == "sign_and_verify":
            for purpose in normalized_purposes:
                active_signers.setdefault(purpose, []).append(key_id)

    for purpose, signers in active_signers.items():
        if len(signers) > 1:
            fail(f"bundle purpose {purpose!r} has multiple active signing keys: {', '.join(sorted(signers))}")

    if not allow_no_active_signer:
        for purpose in sorted(tracked_purposes):
            if not active_signers.get(purpose):
                fail(f"bundle purpose {purpose!r} has no active sign_and_verify key")


def derive_public_key_hex(private_key_path: pathlib.Path) -> str:
    openssl_bin = resolve_openssl()
    result = subprocess.run(
        [
            openssl_bin,
            "pkey",
            "-in",
            str(private_key_path),
            "-pubout",
            "-outform",
            "DER",
        ],
        check=True,
        capture_output=True,
    )
    der = result.stdout
    prefix = bytes.fromhex("302a300506032b6570032100")
    if not der.startswith(prefix) or len(der) != len(prefix) + 32:
        fail(f"{private_key_path}: unexpected Ed25519 public key encoding")
    return der[len(prefix) :].hex()


def ensure_private_key_path(private_key_path: pathlib.Path) -> None:
    if private_key_path.exists():
        fail(f"private key path already exists: {private_key_path}")
    private_key_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        private_key_path.parent.chmod(0o700)
    except OSError:
        pass


def generate_private_key(private_key_path: pathlib.Path) -> str:
    ensure_private_key_path(private_key_path)
    openssl_bin = resolve_openssl()
    subprocess.run(
        [
            openssl_bin,
            "genpkey",
            "-algorithm",
            "Ed25519",
            "-out",
            str(private_key_path),
        ],
        check=True,
    )
    private_key_path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return derive_public_key_hex(private_key_path)


def default_private_key_out(key_id: str) -> pathlib.Path:
    return REPO_ROOT / "keys" / "private" / f"{key_id}.pem"


def print_key_summary(keys: dict[str, dict[str, Any]]) -> None:
    rows = []
    for key_id in sorted(keys):
        entry = keys[key_id]
        rows.append(
            (
                key_id,
                entry["status"],
                entry["usage"],
                ",".join(entry["bundle_purposes"]),
                entry["created_at"],
                entry.get("rotates_after") or "-",
                entry.get("revoked_at") or "-",
            )
        )
    headers = ("key_id", "status", "usage", "purposes", "created_at", "rotates_after", "revoked_at")
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print("  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    for row in rows:
        print("  ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def cmd_list(args: argparse.Namespace) -> None:
    keys = load_keys_dict(args.keys_path)
    validate_keys(keys, allow_no_active_signer=args.allow_no_active_signer)
    if args.json:
        print(json_dumps_sorted(keys))
        return
    print_key_summary(keys)


def json_dumps_sorted(value: Any) -> str:
    import json

    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def cmd_validate(args: argparse.Namespace) -> None:
    keys = load_keys_dict(args.keys_path)
    validate_keys(keys, allow_no_active_signer=args.allow_no_active_signer)
    print(f"managed bundle key policy ok: {args.keys_path}")


def choose_current_signing_key(
    keys: dict[str, dict[str, Any]],
    bundle_purposes: list[str],
    explicit_key_id: str | None,
) -> str:
    matching: set[str] = set()
    for purpose in bundle_purposes:
        matching.update(active_signers_for_purpose(keys, purpose))

    if explicit_key_id is not None:
        if explicit_key_id not in matching:
            fail(
                f"{explicit_key_id}: not an active sign_and_verify key for purposes {', '.join(bundle_purposes)}"
            )
        return explicit_key_id

    if len(matching) != 1:
        fail(
            "rotation requires exactly one current active signing key for the selected purposes; "
            f"found {len(matching)} ({', '.join(sorted(matching)) or 'none'})"
        )
    return next(iter(matching))


def cmd_rotate(args: argparse.Namespace) -> None:
    keys = load_keys_dict(args.keys_path)
    validate_keys(keys)

    if args.new_key_id in keys:
        fail(f"key id already exists: {args.new_key_id}")

    bundle_purposes = args.bundle_purpose or [MANAGED_BUNDLE_PURPOSE]
    created_at = parse_iso_timestamp(args.created_at or utc_now_iso(), "rotate.created_at")
    rotates_after = None
    if args.rotates_after is not None:
        rotates_after = parse_iso_timestamp(args.rotates_after, "rotate.rotates_after")

    current_key_id = choose_current_signing_key(keys, bundle_purposes, args.current_key_id)
    new_private_key_path = args.private_key_out or default_private_key_out(args.new_key_id)
    public_key_hex = generate_private_key(new_private_key_path)

    updated_keys = copy.deepcopy(keys)
    current_key = updated_keys[current_key_id]
    current_key["usage"] = "verify_only"
    if current_key.get("rotates_after") is None:
        current_key["rotates_after"] = created_at

    updated_keys[args.new_key_id] = {
        "publisher": "SpiderVenoms",
        "scheme": SIGNATURE_SCHEME,
        "public_key_hex": public_key_hex,
        "status": "active",
        "usage": "sign_and_verify",
        "bundle_purposes": bundle_purposes,
        "created_at": created_at,
        "rotates_after": rotates_after,
        "revoked_at": None,
        "revocation_reason": None,
    }

    validate_keys(updated_keys)
    write_json(args.keys_path, updated_keys)

    print(f"rotated managed bundle signing key: {current_key_id} -> {args.new_key_id}")
    print(f"private key written to: {new_private_key_path}")


def cmd_revoke(args: argparse.Namespace) -> None:
    keys = load_keys_dict(args.keys_path)
    validate_keys(keys, allow_no_active_signer=args.allow_no_active_signer)

    if args.key_id not in keys:
        fail(f"unknown key id: {args.key_id}")

    updated_keys = copy.deepcopy(keys)
    entry = updated_keys[args.key_id]
    if entry.get("status") == "revoked":
        fail(f"key is already revoked: {args.key_id}")

    revoked_at = parse_iso_timestamp(args.revoked_at or utc_now_iso(), "revoke.revoked_at")
    entry["status"] = "revoked"
    entry["usage"] = "verify_only"
    entry["revoked_at"] = revoked_at
    entry["revocation_reason"] = args.reason

    validate_keys(updated_keys, allow_no_active_signer=args.allow_no_active_signer)
    write_json(args.keys_path, updated_keys)
    print(f"revoked managed bundle key: {args.key_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage SpiderVenoms managed-bundle signing keys.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List managed bundle keys")
    list_parser.add_argument("--keys-path", type=pathlib.Path, default=DEFAULT_KEYS_PATH)
    list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text table")
    list_parser.add_argument(
        "--allow-no-active-signer",
        action="store_true",
        help="Allow key stores with no active sign_and_verify key",
    )
    list_parser.set_defaults(func=cmd_list)

    validate_parser = subparsers.add_parser("validate", help="Validate managed bundle key policy")
    validate_parser.add_argument("--keys-path", type=pathlib.Path, default=DEFAULT_KEYS_PATH)
    validate_parser.add_argument(
        "--allow-no-active-signer",
        action="store_true",
        help="Allow key stores with no active sign_and_verify key",
    )
    validate_parser.set_defaults(func=cmd_validate)

    rotate_parser = subparsers.add_parser("rotate", help="Generate and activate a new signing key")
    rotate_parser.add_argument("--keys-path", type=pathlib.Path, default=DEFAULT_KEYS_PATH)
    rotate_parser.add_argument("--new-key-id", required=True)
    rotate_parser.add_argument("--private-key-out", type=pathlib.Path)
    rotate_parser.add_argument("--current-key-id")
    rotate_parser.add_argument(
        "--bundle-purpose",
        action="append",
        default=[],
        help="Bundle purpose to rotate; repeat for multiple purposes",
    )
    rotate_parser.add_argument("--created-at", help="ISO-8601 timestamp for the new key record")
    rotate_parser.add_argument("--rotates-after", help="Optional ISO-8601 future rotation timestamp")
    rotate_parser.set_defaults(func=cmd_rotate)

    revoke_parser = subparsers.add_parser("revoke", help="Revoke a managed bundle key")
    revoke_parser.add_argument("--keys-path", type=pathlib.Path, default=DEFAULT_KEYS_PATH)
    revoke_parser.add_argument("--key-id", required=True)
    revoke_parser.add_argument("--reason", required=True)
    revoke_parser.add_argument("--revoked-at", help="ISO-8601 timestamp for the revocation event")
    revoke_parser.add_argument(
        "--allow-no-active-signer",
        action="store_true",
        help="Allow revoking the last active sign_and_verify key",
    )
    revoke_parser.set_defaults(func=cmd_revoke)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
