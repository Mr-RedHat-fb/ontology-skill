# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned for 1.1.0
- Consumer-contract enforcement (`ontology-contract.yaml` validation at skill
  activation and write time).
- Domain-type extensions declared by consuming skills.

### Planned for 2.0.0
- Schema-migration framework: `migrate` command and `migrations/` execution.
- Versioned breaking changes to the core schema (if any).

## [1.0.0] — 2026-05-24

Initial release.

### Added
- Typed core schema with 10 entity types (`Person`, `Organization`, `Project`,
  `Task`, `Event`, `Location`, `Document`, `Note`, `Account`, `Device`) and 9
  core relations.
- ULID-prefixed entity identifiers, generated client-side.
- Append-only JSONL storage under `${CLAUDE_PLUGIN_DATA}/`.
- Required provenance fields (`created_by`, `source_skill`) on every entity
  and relation.
- Reference Python implementation with CLI subcommands: `create`, `get`,
  `list`, `query`, `related`, `relate`, `update`, `delete`, `validate`.
- Validation of required properties, enum membership, forbidden property
  names, relation type and cardinality constraints, and acyclic relations.
- Specification for the consumer-contract format
  (`references/consumer-contract.md`) and the schema-migration format
  (`references/migrations.md`).
