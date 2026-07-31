# Vocab consumer contract — Lexicon v0.3

The Vocab desktop application consumes a published lexicon bundle as read-only language knowledge.
The bundle is independent from the desktop binary and may be updated through a controlled update
flow after verification.

## Compatibility and verification

Vocab v0.2 consumers support:

```text
schema_version:  0.2.0
dataset_version: 0.3.x
```

Before importing or replacing a bundle, verify `release-manifest.json` and `manifest.json`
checksums, then require an exact supported schema version. A consumer must reject a bundle with an
unknown schema version; a future schema migration will define its own compatibility path.

The release bundle contains:

```text
lexicon-en-oewn-<version>.sqlite  # preferred runtime artifact
lexicon-en-oewn-<version>.jsonl   # inspection and interchange artifact
manifest.json                     # canonical-artifact checksums and source metadata
release-manifest.json             # checksum index for every bundled file
ATTRIBUTION.md
duplicate-report.json
health-report.json
import-report.json
vocab-compat-<version>.json       # temporary compatibility projection
```

## Preferred SQLite integration

Open the SQLite artifact read-only and enable foreign keys and query-only mode. Treat it as a
replaceable dataset file, not as application state. The primary tables are `lexemes`, `forms`,
`senses`, `definitions`, `examples`, `sources`, and `languages`.

Vocab should query a lexeme through its senses and select an appropriate definition/example in the
application layer. It must retain the lexeme’s `source_id` and `source_sense_key` when displaying
or auditing OEWN-derived content.

The JSONL artifact represents the same canonical records and is suitable for diagnostics or a
future importer, but SQLite is the v0.2 runtime contract.

## Vocab boundary

The lexicon bundle must never store or accept:

- learner mastery, review history, or FSRS/BKT state;
- next-review timestamps, notification settings, or activity data;
- desktop configuration, local paths, or user identifiers.

Those belong in Vocab-owned learner, scheduler, interaction, and settings storage. The legacy
`vocab-compat-*.json` file is an array of `{word, definition, example}` entries only; it discards
lexeme/sense structure and provenance detail, so it is a migration aid rather than a canonical
runtime model.

`health-report.json` is a release-audit artifact, not a runtime dependency. It records source
identity, separate record counts, part-of-speech coverage, example/gloss coverage, provenance
gaps, and normalized-input duplicate counts. The v0.3 release process requires it to match the
committed OEWN baseline exactly.
