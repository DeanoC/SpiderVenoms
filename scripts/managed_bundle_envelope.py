#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import pathlib
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_RELEASE_PATH = REPO_ROOT / "assets" / "bundles" / "managed-local" / "release.json"
DEFAULT_KEYS_PATH = REPO_ROOT / "keys" / "trusted-managed-bundle-keys.json"
SIGNATURE_SCHEME = "ed25519-sha256-v1"


def fail(message: str) -> "NoReturn":
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def canonical_json(value: Any) -> str:
    if isinstance(value, dict):
        parts: list[str] = []
        for key in sorted(value):
            if key in {"digest", "signature"}:
                continue
            parts.append(f"{json.dumps(key, ensure_ascii=False, separators=(',', ':'))}:{canonical_json(value[key])}")
        return "{" + ",".join(parts) + "}"
    if isinstance(value, list):
        return "[" + ",".join(canonical_json(item) for item in value) + "]"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False)


def payload_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def payload_digest_hex(value: Any) -> str:
    return hashlib.sha256(payload_bytes(value)).hexdigest()


def raw_public_key_pem(public_key_hex: str) -> str:
    raw = bytes.fromhex(public_key_hex)
    if len(raw) != 32:
        fail("expected 32-byte Ed25519 public key")
    subject_public_key_info = bytes.fromhex("302a300506032b6570032100") + raw
    body = base64.b64encode(subject_public_key_info).decode("ascii")
    return "-----BEGIN PUBLIC KEY-----\n" + body + "\n-----END PUBLIC KEY-----\n"


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text())


def write_json(path: pathlib.Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def load_trusted_keys(keys_path: pathlib.Path) -> dict[str, dict[str, str]]:
    keys = load_json(keys_path)
    if not isinstance(keys, dict) or not keys:
        fail(f"trusted key store is empty: {keys_path}")
    return keys


def resolve_openssl() -> str:
    candidates = [
        os.environ.get("OPENSSL_BIN"),
        "/opt/homebrew/opt/openssl@3/bin/openssl",
        "/usr/local/opt/openssl@3/bin/openssl",
        shutil.which("openssl"),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = pathlib.Path(candidate)
        if not path.exists():
            continue
        version_result = subprocess.run(
            [str(path), "version"],
            check=False,
            capture_output=True,
            text=True,
        )
        version_output = (version_result.stdout + version_result.stderr).strip()
        if "OpenSSL" in version_output and "LibreSSL" not in version_output:
            return str(path)
    fail("OpenSSL 3 is required for Ed25519 managed-bundle signing and verification")


def sign_digest(private_key_path: pathlib.Path, digest_hex: str) -> str:
    openssl_bin = resolve_openssl()
    digest_bytes = bytes.fromhex(digest_hex)
    with tempfile.TemporaryDirectory() as tmpdir:
        digest_path = pathlib.Path(tmpdir) / "digest.bin"
        signature_path = pathlib.Path(tmpdir) / "signature.bin"
        digest_path.write_bytes(digest_bytes)
        subprocess.run(
            [
                openssl_bin,
                "pkeyutl",
                "-sign",
                "-inkey",
                str(private_key_path),
                "-rawin",
                "-in",
                str(digest_path),
                "-out",
                str(signature_path),
            ],
            check=True,
        )
        return base64.b64encode(signature_path.read_bytes()).decode("ascii")


def verify_digest_signature(public_key_hex: str, digest_hex: str, signature_b64: str) -> None:
    openssl_bin = resolve_openssl()
    digest_bytes = bytes.fromhex(digest_hex)
    signature = base64.b64decode(signature_b64, validate=True)
    with tempfile.TemporaryDirectory() as tmpdir:
        digest_path = pathlib.Path(tmpdir) / "digest.bin"
        signature_path = pathlib.Path(tmpdir) / "signature.bin"
        public_key_path = pathlib.Path(tmpdir) / "public.pem"
        digest_path.write_bytes(digest_bytes)
        signature_path.write_bytes(signature)
        public_key_path.write_text(raw_public_key_pem(public_key_hex))
        subprocess.run(
            [
                openssl_bin,
                "pkeyutl",
                "-verify",
                "-pubin",
                "-inkey",
                str(public_key_path),
                "-rawin",
                "-in",
                str(digest_path),
                "-sigfile",
                str(signature_path),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def sign_object(value: dict[str, Any], key_id: str, private_key_path: pathlib.Path) -> None:
    digest_hex = payload_digest_hex(value)
    value["digest"] = f"sha256:{digest_hex}"
    signature_b64 = sign_digest(private_key_path, digest_hex)
    value["signature"] = {
        "scheme": SIGNATURE_SCHEME,
        "key_id": key_id,
        "value": signature_b64,
    }


def verify_object(value: dict[str, Any], trusted_keys: dict[str, dict[str, str]], label: str) -> None:
    trust = value.get("trust")
    if not isinstance(trust, dict):
        fail(f"{label}: missing trust object")
    if str(trust.get("mode", "")).strip() == "unsigned":
        fail(f"{label}: unsigned trust mode is not allowed")

    digest = value.get("digest")
    if not isinstance(digest, str) or not digest.startswith("sha256:"):
        fail(f"{label}: invalid digest")
    digest_hex = digest.split(":", 1)[1]
    if len(digest_hex) != 64:
        fail(f"{label}: invalid sha256 digest length")

    expected_digest_hex = payload_digest_hex(value)
    if digest_hex != expected_digest_hex:
        fail(f"{label}: digest mismatch")

    signature = value.get("signature")
    if not isinstance(signature, dict):
        fail(f"{label}: missing signature object")
    scheme = signature.get("scheme")
    key_id = signature.get("key_id")
    signature_value = signature.get("value")
    if scheme != SIGNATURE_SCHEME:
        fail(f"{label}: unsupported signature scheme: {scheme!r}")
    if not isinstance(key_id, str) or not key_id:
        fail(f"{label}: missing signature key_id")
    trusted_key = trusted_keys.get(key_id)
    if trusted_key is None:
        fail(f"{label}: untrusted key id: {key_id}")
    if trusted_key.get("scheme") != SIGNATURE_SCHEME:
        fail(f"{label}: trusted key store scheme mismatch for {key_id}")
    if not isinstance(signature_value, str) or not signature_value:
        fail(f"{label}: missing signature value")
    verify_digest_signature(trusted_key["public_key_hex"], digest_hex, signature_value)


def verify_bundle(release_path: pathlib.Path, keys_path: pathlib.Path) -> None:
    trusted_keys = load_trusted_keys(keys_path)
    release = load_json(release_path)
    if not isinstance(release, dict):
        fail(f"{release_path}: release root must be an object")
    verify_object(release, trusted_keys, str(release_path))

    bundle_root = release_path.parent
    packages = release.get("packages")
    if not isinstance(packages, list):
        fail(f"{release_path}: packages must be an array")

    for package in packages:
        if not isinstance(package, dict):
            fail(f"{release_path}: package entry must be an object")
        package_id = package.get("package_id", "<unknown>")
        verify_object(package, trusted_keys, f"{release_path} package {package_id}")

        manifest_rel_path = package.get("manifest_path")
        if not isinstance(manifest_rel_path, str) or not manifest_rel_path:
            fail(f"{release_path} package {package_id}: missing manifest_path")
        manifest_path = bundle_root / manifest_rel_path
        if not manifest_path.is_file():
            fail(f"{release_path} package {package_id}: manifest missing at {manifest_path}")
        manifest = load_json(manifest_path)
        if not isinstance(manifest, dict):
            fail(f"{manifest_path}: manifest root must be an object")
        verify_object(manifest, trusted_keys, str(manifest_path))

        for field in ("package_id", "release_version", "venom_id", "kind", "channel"):
            if field in package and manifest.get(field) != package.get(field):
                fail(f"{manifest_path}: {field} does not match release entry for {package_id}")


def sign_bundle(release_path: pathlib.Path, keys_path: pathlib.Path, key_id: str, private_key_path: pathlib.Path) -> None:
    trusted_keys = load_trusted_keys(keys_path)
    if key_id not in trusted_keys:
        fail(f"unknown signing key id: {key_id}")

    release = load_json(release_path)
    if not isinstance(release, dict):
        fail(f"{release_path}: release root must be an object")

    bundle_root = release_path.parent
    packages = release.get("packages")
    if not isinstance(packages, list):
        fail(f"{release_path}: packages must be an array")

    for package in packages:
        if not isinstance(package, dict):
            fail(f"{release_path}: package entry must be an object")

        manifest_rel_path = package.get("manifest_path")
        if not isinstance(manifest_rel_path, str) or not manifest_rel_path:
            fail("package entry missing manifest_path")
        manifest_path = bundle_root / manifest_rel_path
        manifest = load_json(manifest_path)
        if not isinstance(manifest, dict):
            fail(f"{manifest_path}: manifest root must be an object")
        sign_object(manifest, key_id, private_key_path)
        write_json(manifest_path, manifest)

        sign_object(package, key_id, private_key_path)

    sign_object(release, key_id, private_key_path)
    write_json(release_path, release)

    verify_bundle(release_path, keys_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sign or verify the SpiderVenoms managed bundle envelope.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify_parser = subparsers.add_parser("verify", help="Verify release and manifest signatures")
    verify_parser.add_argument("--release-path", type=pathlib.Path, default=DEFAULT_RELEASE_PATH)
    verify_parser.add_argument("--keys-path", type=pathlib.Path, default=DEFAULT_KEYS_PATH)

    sign_parser = subparsers.add_parser("sign", help="Sign release and manifest metadata")
    sign_parser.add_argument("--release-path", type=pathlib.Path, default=DEFAULT_RELEASE_PATH)
    sign_parser.add_argument("--keys-path", type=pathlib.Path, default=DEFAULT_KEYS_PATH)
    sign_parser.add_argument("--key-id", required=True)
    sign_parser.add_argument("--private-key", type=pathlib.Path, required=True)

    args = parser.parse_args()
    if args.command == "verify":
        verify_bundle(args.release_path.resolve(), args.keys_path.resolve())
        print(f"managed bundle signature verification ok: {args.release_path}")
        return
    if args.command == "sign":
        sign_bundle(args.release_path.resolve(), args.keys_path.resolve(), args.key_id, args.private_key.resolve())
        print(f"managed bundle signed: {args.release_path}")
        return
    fail(f"unsupported command: {args.command}")


if __name__ == "__main__":
    main()
