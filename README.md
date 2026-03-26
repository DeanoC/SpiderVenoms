# SpiderVenoms

First-party Venom bundle metadata, manifests, and release assets for the Spider ecosystem.

Current scope:

- managed local capability venoms for Spiderweb-hosted nodes
- first-party package/release metadata for:
  - `terminal`
  - `git`
  - `search_code`
  - `computer`
  - `browser`
- signed Ed25519 bundle envelopes verified by Spiderweb's managed local node loader

This repo is intentionally package-first. Runtime implementations still live in the
existing repos during the migration, but Spiderweb now reads managed capability
manifests and release metadata from here.

## Release line

- Current public release line: `0.5.8`
- Release tags use `vX.Y.Z`
- Default policy is patch-first release bumps

See [docs/release-policy.md](docs/release-policy.md) for the maintainer workflow.

## Release automation

- CI validates version sync, builds the bundle, and exercises the release packager.
- Tagged releases publish Linux and macOS managed-bundle archives for the current release line.
- Tagged releases also publish `spidervenoms-release-facts.json` for SpiderVenomRegistry generation, resolved against the published release checksum assets.
- Maintainers sign `release.json` and `manifests/*.json` with `./scripts/managed_bundle_envelope.py sign`.
- Maintainers manage key rotation and revocation with `./scripts/manage_managed_bundle_keys.py`.
- Trusted keys now carry explicit policy metadata:
  - `status`: `active` or `revoked`
  - `usage`: `sign_and_verify` or `verify_only`
  - `bundle_purposes`: currently `managed_local_bundle`

Key workflow helpers:

```bash
./scripts/manage_managed_bundle_keys.py list
./scripts/manage_managed_bundle_keys.py validate
./scripts/manage_managed_bundle_keys.py rotate --new-key-id spidervenoms-2026-04 --private-key-out ./keys/private/spidervenoms-2026-04.pem
./scripts/manage_managed_bundle_keys.py revoke --key-id spidervenoms-2026-04 --reason "Compromised signing host"
```

Packaging helper:

```bash
./scripts/package-spidervenoms-linux-release.sh --out-dir ./dist
```
