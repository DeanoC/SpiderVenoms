# Release Policy

SpiderVenoms now uses a patch-first versioning policy.

## Current baseline

- Current public release line: `0.5.8`
- Release tags must use the format `vX.Y.Z`
- `build.zig.zon` is the canonical version source

## Default rule

For normal releases, increment only the lowest portion of the version:

- `0.5.0 -> 0.5.1`
- `0.5.1 -> 0.5.3`

This is the default for routine bundle metadata updates, packaging fixes, compatibility work, and normal iterative delivery.

## Explicit bigger releases

Minor or major bumps are allowed, but they must be explicit:

- Minor bump example: `0.5.9 -> 0.6.0`
- Major bump example: `0.9.4 -> 1.0.0`

Use a bigger bump only when we are intentionally marking a larger release boundary, such as:

- a major ecosystem milestone
- a meaningful venom contract or compatibility shift
- a planned public release train change

When doing this:

- call it out explicitly in the release PR or release notes
- update the changelog with the rationale
- use `scripts/bump-version.sh --minor --explicit` or `--major --explicit`

## Maintainer workflow

Default patch bump:

```bash
./scripts/bump-version.sh
```

Explicit minor bump:

```bash
./scripts/bump-version.sh --minor --explicit
```

Explicit major bump:

```bash
./scripts/bump-version.sh --major --explicit
```

Version consistency check:

```bash
./scripts/check-version-sync.sh
```

Managed key policy validation:

```bash
./scripts/manage_managed_bundle_keys.py validate
```

## Key rotation and revocation

Generate and activate a new signing key while demoting the current active key to `verify_only`:

```bash
./scripts/manage_managed_bundle_keys.py rotate \
  --new-key-id spidervenoms-2026-04 \
  --private-key-out ./keys/private/spidervenoms-2026-04.pem
```

This will:

- generate a new Ed25519 private key
- add the matching public key to `keys/trusted-managed-bundle-keys.json`
- make the new key `active` + `sign_and_verify`
- demote the previous active signing key to `verify_only`

Inspect the current key policy:

```bash
./scripts/manage_managed_bundle_keys.py list
```

Revoke a key:

```bash
./scripts/manage_managed_bundle_keys.py revoke \
  --key-id spidervenoms-2026-04 \
  --reason "Compromised signing host"
```

Notes:

- generated private keys should live outside Git; `keys/private/` is ignored for local maintainer workflows
- revoking the last active signing key is blocked unless you pass `--allow-no-active-signer`
- after rotation, re-sign `release.json` and `manifests/*.json` with the new key before publishing the next release

## Files that must stay aligned

- `build.zig.zon`
- top changelog entry in `CHANGELOG.md`
- `assets/bundles/managed-local/release.json`
- `assets/bundles/managed-local/manifests/*.json`

Maintainer tooling validates these before release.
