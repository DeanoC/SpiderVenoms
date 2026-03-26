# Release Policy

SpiderVenoms now uses a patch-first versioning policy.

## Current baseline

- Current public release line: `0.5.1`
- Release tags must use the format `vX.Y.Z`
- `build.zig.zon` is the canonical version source

## Default rule

For normal releases, increment only the lowest portion of the version:

- `0.5.0 -> 0.5.1`
- `0.5.1 -> 0.5.2`

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

## Files that must stay aligned

- `build.zig.zon`
- top changelog entry in `CHANGELOG.md`
- `assets/bundles/managed-local/release.json`
- `assets/bundles/managed-local/manifests/*.json`

Maintainer tooling validates these before release.
