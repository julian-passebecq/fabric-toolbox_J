# Native release bundles

M04 introduces an offline release boundary for Fabric Ops Studio. Native Fabric definitions are treated as opaque files. Studio validates the project contract and filesystem paths, but it does not reinterpret or regenerate native definitions.

## Workflow

```text
Configure
  -> Validate project contract
  -> Build immutable native bundle
  -> Verify exact file/resource scope
  -> Review profile + workspace + revision + hashes
  -> Approve the exact immutable bundle
  -> Publish (not implemented in M04)
  -> Verify remote state (future milestone)
```

A release approval is **not executable**. There is no publish command in M04.

## Bundle identity

A bundle records and verifies:

- project ID and project-schema version
- selected profile and revision
- target workspace display name
- capacity and identity references
- deployment owner
- exact managed resource set
- every included native file path, byte size, and SHA-256
- per-resource SHA-256
- canonical project SHA-256
- reviewed scope SHA-256
- final ZIP SHA-256 returned by the builder/verifier

External resources remain in release metadata but their native files are not packaged.

The ZIP writer uses fixed metadata and sorted entries. Building the same project/profile/revision/content produces the same bundle bytes in the same runtime.

## Ownership

A project profile has exactly one declared deployment owner.

- `studio-runner`: Studio may create an offline approval record for the immutable bundle.
- `native-git`: Studio refuses publish approval for that profile.

This prevents the Studio runner and Fabric native Git integration from silently competing for the same workspace.

## Safety

- existing release files are never overwritten
- project definitions must remain inside the trusted project root
- symlinks inside managed definitions are rejected
- ZIP path traversal and duplicate entries are rejected
- imported files must match the reviewed hashes and exact artifact set
- import targets must not already exist
- imports are staged and renamed into place only after verification
- inline credentials remain prohibited by the project contract
- M04 performs no Fabric network request and has no publish side effect

## CLI

From the repository root, using the backend environment:

```powershell
python studio/scripts/release_bundle.py build .\project\fabric-project.yaml `
  --project-root .\project `
  --profile dev `
  --revision git:abc123 `
  --output .\releases\foil-dev-abc123.zip

python studio/scripts/release_bundle.py verify .\releases\foil-dev-abc123.zip
python studio/scripts/release_bundle.py challenge .\releases\foil-dev-abc123.zip
```

After reviewing the exact challenge:

```powershell
python studio/scripts/release_bundle.py approve .\releases\foil-dev-abc123.zip `
  --confirmation "APPROVE <exact challenge text>"
```

The returned approval has `executable: false`.

To round-trip a verified release back to a new local directory:

```powershell
python studio/scripts/release_bundle.py import .\releases\foil-dev-abc123.zip `
  --destination .\imported\foil
```

The imported project contains the canonical project snapshot, the exact native artifact bytes, and `.studio-release.json` with the reviewed release descriptor.
