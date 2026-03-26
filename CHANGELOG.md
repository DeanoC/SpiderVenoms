# Changelog

All notable changes to this project are documented in this file.

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
