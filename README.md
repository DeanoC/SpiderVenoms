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

- Current public release line: `0.5.3`
- Release tags use `vX.Y.Z`
- Default policy is patch-first release bumps

See [docs/release-policy.md](docs/release-policy.md) for the maintainer workflow.

## Release automation

- CI validates version sync, builds the bundle, and exercises the release packager.
- Tagged releases publish Linux and macOS managed-bundle archives for the current release line.
- Maintainers sign `release.json` and `manifests/*.json` with `./scripts/managed_bundle_envelope.py sign`.

Packaging helper:

```bash
./scripts/package-spidervenoms-linux-release.sh --out-dir ./dist
```
