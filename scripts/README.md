# Release Scripts

Maintainer helpers for `SpiderVenoms` release preparation and packaging.

## Versioning

Patch releases are the default path:

```bash
./scripts/bump-version.sh
```

Version consistency check:

```bash
./scripts/check-version-sync.sh
```

See [../docs/release-policy.md](/Users/deanocalver/Documents/Projects/Spider/SpiderVenoms/docs/release-policy.md) for the full release policy.

## Release Packaging

Linux managed-bundle archive:

```bash
./scripts/package-spidervenoms-linux-release.sh --out-dir ./dist
```

This produces:

- `dist/spidervenoms-managed-local-linux-<arch>.tar.gz`
- `dist/spidervenoms-managed-local-linux-<arch>.tar.gz.sha256`

Published Linux archives are supported for:

- `linux/x86_64`
- `linux/arm64`

If `Spiderweb` is not checked out next to `SpiderVenoms`, set `SPIDERWEB_REPO_DIR` to its checkout path before running the packager.

macOS managed-bundle archive:

```bash
./scripts/package-spidervenoms-macos-release.sh --out-dir ./dist
```

This produces:

- `dist/spidervenoms-managed-local-macos-<arch>.tar.gz`
- `dist/spidervenoms-managed-local-macos-<arch>.tar.gz.sha256`
