# Changelog

All notable changes to this project are documented in this file.

## 0.5.5 - 2026-03-26

### Release Automation
- Fixed the managed-bundle signature verifier to prefer OpenSSL 3 explicitly, which unblocks macOS GitHub runners from validating Ed25519 bundle signatures during CI and release jobs.
- Updated the macOS workflows to expose a compatible OpenSSL 3 toolchain before running version-sync and release verification.

## 0.5.4 - 2026-03-26

### Bundle Trust
- Replaced the managed-local bundle's placeholder signature envelope with real `ed25519-sha256-v1` digests and signatures across `release.json` and all published manifests.
- Added maintainer signing and verification tooling so version bumps can re-sign the bundle metadata without hand-editing digests.
- Added a trusted-key registry for the managed-local bundle and CI-ready verification hooks for the signed envelope.

## 0.5.3 - 2026-03-26

### Linux Release Coverage
- Added native Linux `arm64` managed-bundle release archives alongside `x86_64` so downstream consumers can pin SpiderVenoms on both supported Linux architectures.
- Updated CI and tag-release automation to build, verify, and publish both Linux architectures with normalized `arm64`/`x86_64` artifact names.

## 0.5.2 - 2026-03-26

### Release Packaging
- Added a macOS managed-bundle release archive alongside the Linux archive so downstream consumers can pin a published SpiderVenoms artifact on both platforms.
- Extended CI and tag-release automation to build, verify, and publish the macOS managed-local bundle archive.

## 0.5.1 - 2026-03-26

### Release Automation
- Fixed the GitHub Actions archive verification step to inspect tar contents without tripping `pipefail` on `grep -q` early-exit behavior.
- Re-ran the standalone `SpiderVenoms` tag-release path using the patch-first release policy.

## 0.5.0 - 2026-03-26

### Release and Versioning
- Reset the public SpiderVenoms release line to `0.5.0`.
- Standardized on patch-first version bumps for normal releases, with explicit minor or major bumps only for larger milestones.
- Added maintainer tooling to keep bundle metadata, manifests, and changelog versions aligned.

### Managed Local Bundle
- Published the managed-local bundle metadata at the `0.5.0` baseline for `terminal`, `git`, `search_code`, `computer`, and `browser`.
- Kept the signed-release envelope placeholders in sync across the bundle release and per-package manifests.
