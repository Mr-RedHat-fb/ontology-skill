---
name: ontology
description: Shared agent memory as a typed knowledge graph stored on the operator's filesystem. Use when an agent needs to remember facts across sessions or share remembered facts with other agents in the same ecosystem. Trigger on "remember that", "what do I know about X", "link X to Y", "show what's known about Y", "forget X", or when a skill needs to read or write structured cross-session state. Complementary to the AI client's native memory: native memory captures style and preferences, ontology captures facts.
---

# Ontology

Shared agent memory as a typed knowledge graph. A local, structured notebook
that agents read and write to so they remember facts across sessions and across
tools.

## What this is — and isn't

**This is** a local file the operator owns, holding structured facts ("Alice at
example.com is the contact for the website-redesign project, deadline June
15"). Multiple agents — different AI clients, CLI assistants, other tools — can
read and write the same file using the schema defined here.

**This is not**:

- A source of truth for external systems. Issue trackers hold tickets, task
  apps hold tasks, calendar apps hold events. Ontology holds what the agents
  want to *remember* about the operator's world. Drift between ontology and
  external systems is expected.
- A replacement for the AI client's own memory. Native memory captures style
  and preferences. Ontology captures facts. The two layer; they don't conflict.
- A general-purpose database. Append-only, single-writer per session, queried
  by tools that know the schema.

## Core model

Every record is an **entity** with a stable id, a type, properties, and
explicit provenance:

```json
{
  "id": "task_01HQX9N7M2VG8FZK0AYE3HXBQR",
  "type": "Task",
  "properties": {
    "title": "Send quarterly report",
    "due": "2026-06-15",
    "status": "open"
  },
  "provenance": {
    "created_by": "claude",
    "source_skill": "plan-underhead@1.0.0",
    "session_ref": "chat:abc123",
    "external_id": "gtasks:MTQzNzg..."
  },
  "created": "2026-05-24T15:00:00+02:00",
  "updated": "2026-05-24T15:00:00+02:00"
}
```

Entities are linked through **relations**:

```json
{
  "from": "task_01HQX9N7M2VG8FZK0AYE3HXBQR",
  "rel": "for_project",
  "to": "proj_01HQA8M1...",
  "provenance": {
    "created_by": "claude",
    "source_skill": "plan-underhead@1.0.0"
  },
  "created": "2026-05-24T15:00:00+02:00"
}
```

`provenance` is required on every entity and every relation. It is how multiple
agents coexist in the same graph without losing track of who wrote what.

## Storage

Data lives under `${CLAUDE_PLUGIN_DATA}/` so it persists across plugin updates
and is removed cleanly on uninstall:

- `graph.jsonl` — append-only log of all create / update / delete / relate
  operations
- `schema.yaml` — active schema for this installation

The append-only log is the canonical representation. Any in-memory or indexed
view is derived from it. Treat the file as a journal, not a snapshot.

## IDs

Every entity id is a **ULID with a short type prefix**:
`task_01HQX9N7M2VG8FZK0AYE3HXBQR`, `proj_01HQA...`, `person_01HQY...`.

The type prefix is human-readable and helps disambiguate at a glance. The ULID
handles uniqueness and approximate chronological ordering. Implementations must
not generate IDs from any other scheme.

## Schema: core + domain

The schema is layered. The **core schema** ships with this skill and defines a
small, stable vocabulary every agent can rely on. **Domain schemas** are
declared by consuming skills and extend the core without modifying it.

### Core types

The core types are:

- `Person` — someone the operator knows of
- `Organization` — a company, agency, or group
- `Project` — a piece of work the operator is engaged in
- `Task` — something to be done, with a status
- `Event` — something happening at a time
- `Location` — a place
- `Document` — a file, URL, or document reference
- `Note` — freeform text the operator wanted remembered
- `Account` — a service account or identity
- `Device` — a physical or virtual machine

Full field definitions and constraints are in `references/core-types.md`.

The core types are deliberately small. Anything more specific belongs in a
domain schema.

### Domain extensions (specification only in v1.0.0)

Consuming skills declare their own types and relations through a contract
file. For example, a legal skill might add:

```yaml
domain_types: [CourtCase]

types:
  CourtCase:
    extends: Project
    required: [case_number, court]
    properties:
      case_number: string
      court: string
      respondent: ref<Person>
```

The contract mechanism is described in `references/consumer-contract.md`. In
v1.0.0 the contract format is **specified but not enforced** — consuming skills
may author contract files now, and enforcement arrives in v1.1.0. See
`CHANGELOG.md`.

## Provenance

Every entity and relation carries provenance fields:

- `created_by` — agent identifier (`claude`, `alfred`, `chatgpt`, etc.)
- `source_skill` — the skill that produced the write, including version
  (`plan-underhead@1.0.0`)
- `session_ref` — optional reference for tracing back to the originating
  conversation
- `external_id` — optional identifier in an external system this record mirrors

Provenance is required. Records without `created_by` and `source_skill` are
rejected.

## Schema versions

The schema has its own semantic version (`schema_version` in `schema.yaml`).

- **Patch**: clarification, documentation, no shape change.
- **Minor**: additive change (new optional field, new type, new relation).
- **Major**: breaking change (removed field, changed type, renamed relation).

Major version changes require a migration. The migration framework is
documented in `references/migrations.md` and ships as **specification only** in
v1.0.0; the `migrate` command arrives in v2.0.0.

## Consumer contract

A skill that uses ontology declares its contract in its own repo, in a file
named `ontology-contract.yaml`. Minimal example:

```yaml
ontology_version: ~1.0.0
reads: [Task, Project, Person]
writes: [Task, Note]
domain_types: []
```

Full specification: `references/consumer-contract.md`.

The contract is documentation in v1.0.0 and enforced runtime input in v1.1.0.
Consuming skills should ship their contract file from v1.0.0 onward to ease the
later transition.

## Workflows

The skill ships with a reference implementation in
`skills/ontology/scripts/ontology.py`. Other implementations are welcome as long
as they honour the contract defined here.

The reference implementation requires Python 3.10+ and PyYAML
(`pip install pyyaml`).

Set the agent identifier and source skill on every write:

```bash
SCRIPT="${CLAUDE_PLUGIN_ROOT}/skills/ontology/scripts/ontology.py"
AGENT=claude
SKILL=plan-underhead@1.0.0
```

### Create

```bash
python3 "$SCRIPT" create \
  --type Person \
  --props '{"name":"Alice","email":"alice@example.com"}' \
  --agent "$AGENT" --skill "$SKILL"
```

Output is the new entity's id on stdout.

### Get and list

```bash
python3 "$SCRIPT" get --id person_01HQY...
python3 "$SCRIPT" list --type Task
python3 "$SCRIPT" query --type Task --where '{"status":"open"}'
```

### Relate

```bash
python3 "$SCRIPT" relate \
  --from proj_01HQA... --rel has_task --to task_01HQX... \
  --agent "$AGENT" --skill "$SKILL"
```

### Update and delete

```bash
python3 "$SCRIPT" update --id task_01HQX... \
  --props '{"status":"done"}' \
  --agent "$AGENT" --skill "$SKILL"

python3 "$SCRIPT" delete --id task_01HQX... \
  --agent "$AGENT" --skill "$SKILL"
```

Delete is a tombstone in the append-only log, not a removal of historical
records.

### Validate

```bash
python3 "$SCRIPT" validate
```

Validates required properties, enum membership, forbidden properties, relation
type and cardinality, and acyclic constraints where declared.

## Boundaries

Do **not** put in ontology:

- Secrets, passwords, API tokens, private keys. Use `Account` for the public
  surface and reference a vault for the secret.
- Source code, transcripts, large binary blobs. Reference them by path or url.
- Mirror copies of external state purely for performance. Ontology is a memory
  layer, not a cache.
- Free-form journal entries with no structure. Use the operator's preferred
  note-taking tool.

## v1.0.0 scope

**Implemented**:

- Core type vocabulary and validation
- ULID-prefixed entity ids
- Append-only JSONL storage under `${CLAUDE_PLUGIN_DATA}/`
- Required provenance on all writes
- CLI: `create`, `get`, `list`, `query`, `relate`, `update`, `delete`,
  `validate`

**Specification only (deferred)**:

- Domain type extensions declared by consuming skills (v1.1.0)
- Consumer-contract enforcement (v1.1.0)
- Migration framework (v2.0.0)

See `CHANGELOG.md` for the version timeline.

## References

- `references/core-types.md` — full type definitions and core relations
- `references/consumer-contract.md` — contract specification for consuming
  skills (specification-only in v1.0.0)
- `references/migrations.md` — schema migration patterns (specification-only in
  v1.0.0)
