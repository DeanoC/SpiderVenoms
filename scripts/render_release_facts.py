#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.request


def fail(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: pathlib.Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        fail(f"missing json file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"{path}: invalid json: {exc}")


def read_sha256(path: pathlib.Path) -> str:
    try:
        line = path.read_text(encoding="utf-8").splitlines()[0].strip()
    except FileNotFoundError:
        fail(f"missing checksum file: {path}")
    except IndexError:
        fail(f"checksum file is empty: {path}")
    sha = line.split()[0].strip()
    if len(sha) != 64:
        fail(f"{path}: expected sha256 checksum, got {sha!r}")
    return sha


def read_sha256_text(text: str, source: str) -> str:
    line = text.splitlines()[0].strip() if text.splitlines() else ""
    sha = line.split()[0].strip() if line else ""
    if len(sha) != 64:
        fail(f"{source}: expected sha256 checksum, got {sha!r}")
    return sha


def fetch_sha256(url: str) -> str:
    try:
        with urllib.request.urlopen(url) as response:
            payload = response.read().decode("utf-8")
    except Exception as exc:
        fail(f"failed to fetch checksum asset {url}: {exc}")
    return read_sha256_text(payload, url)


def artifact_url(repo: str, version: str, filename: str) -> str:
    return f"https://github.com/{repo}/releases/download/v{version}/{filename}"


def detect_platforms_from_filename(filename: str) -> tuple[str, str]:
    stem = filename
    if stem.endswith(".tar.gz"):
        stem = stem[: -len(".tar.gz")]
    parts = stem.split("-")
    if len(parts) < 2:
        fail(f"unexpected artifact filename: {filename}")
    return parts[-2], parts[-1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Render machine-readable SpiderVenoms release facts.")
    parser.add_argument("--repo-root", default=None, help="SpiderVenoms repo root")
    parser.add_argument("--release-json", default=None, help="Path to managed-local release.json")
    parser.add_argument("--dist-dir", default=None, help="Directory containing packaged release archives")
    parser.add_argument("--out", required=True, help="Output path")
    parser.add_argument("--repo", default="DeanoC/SpiderVenoms", help="GitHub repo slug for published artifacts")
    parser.add_argument("--published-at", default=None, help="Published timestamp in RFC3339/ISO8601 form")
    parser.add_argument(
        "--resolve-published-checksums",
        action="store_true",
        help="Resolve artifact sha256 values from published GitHub release checksum assets",
    )
    args = parser.parse_args()

    repo_root = pathlib.Path(args.repo_root or pathlib.Path(__file__).resolve().parents[1]).resolve()
    release_json_path = pathlib.Path(
        args.release_json or repo_root / "assets" / "bundles" / "managed-local" / "release.json"
    ).resolve()
    dist_dir = pathlib.Path(args.dist_dir or repo_root / "dist").resolve()
    out_path = pathlib.Path(args.out).resolve()

    release = load_json(release_json_path)
    if not isinstance(release, dict):
        fail(f"{release_json_path}: expected object")

    bundle_id = release.get("bundle_id")
    release_version = release.get("release_version") or release.get("version")
    channel = release.get("channel")
    packages = release.get("packages")
    if not isinstance(bundle_id, str) or not bundle_id:
        fail(f"{release_json_path}: missing bundle_id")
    if not isinstance(release_version, str) or not release_version:
        fail(f"{release_json_path}: missing release_version")
    if not isinstance(channel, str) or not channel:
        fail(f"{release_json_path}: missing channel")
    if not isinstance(packages, list) or not packages:
        fail(f"{release_json_path}: missing packages array")

    artifacts: list[dict[str, object]] = []
    for archive_path in sorted(dist_dir.glob("spidervenoms-managed-local-*.tar.gz")):
        sha_path = archive_path.with_name(f"{archive_path.name}.sha256")
        os_name, arch = detect_platforms_from_filename(archive_path.name)
        sha256_asset_url = artifact_url(args.repo, release_version, sha_path.name)
        sha256 = (
            fetch_sha256(sha256_asset_url)
            if args.resolve_published_checksums
            else read_sha256(sha_path)
        )
        artifacts.append(
            {
                "os": os_name,
                "arch": arch,
                "filename": archive_path.name,
                "url": artifact_url(args.repo, release_version, archive_path.name),
                "sha256": sha256,
                "size_bytes": archive_path.stat().st_size,
                "sha256_asset_url": sha256_asset_url,
            }
        )

    if not artifacts:
        fail(f"no packaged release archives found in {dist_dir}")

    package_ids: list[str] = []
    projected_packages: list[dict[str, object]] = []
    for package in packages:
        if not isinstance(package, dict):
            fail(f"{release_json_path}: package entry must be an object")
        package_id = package.get("package_id")
        venom_id = package.get("venom_id")
        kind = package.get("kind")
        package_release_version = package.get("release_version") or package.get("version")
        package_channel = package.get("channel") or channel
        if not isinstance(package_id, str) or not package_id:
            fail(f"{release_json_path}: package entry missing package_id")
        if not isinstance(venom_id, str) or not venom_id:
            fail(f"{release_json_path}: package {package_id} missing venom_id")
        if not isinstance(kind, str) or not kind:
            fail(f"{release_json_path}: package {package_id} missing kind")
        if not isinstance(package_release_version, str) or not package_release_version:
            fail(f"{release_json_path}: package {package_id} missing release_version")
        package_ids.append(package_id)
        projected_packages.append(
            {
                "package_id": package_id,
                "venom_id": venom_id,
                "kind": kind,
                "release_version": package_release_version,
                "channel": package_channel,
                "digest": package.get("digest"),
                "signature": package.get("signature"),
                "trust": package.get("trust"),
            }
        )

    payload = {
        "schema_version": "spidervenoms-release-facts-v1",
        "publisher": "SpiderVenoms",
        "bundle_id": bundle_id,
        "release_version": release_version,
        "channel": channel,
        "published_at": args.published_at or utc_now(),
        "package_ids": package_ids,
        "packages": projected_packages,
        "artifacts": artifacts,
        "release_manifest": {
            "path": str(release_json_path.relative_to(repo_root)),
            "digest": release.get("digest"),
            "signature": release.get("signature"),
            "trust": release.get("trust"),
        },
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"release facts written: {out_path}")


if __name__ == "__main__":
    main()
