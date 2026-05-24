# Consumer contract specification

> **Status in v1.0.0**: specification only. Contract files are recognised by
> the reference implementation but not enforced at write time. Enforcement
> arrives in v1.1.0. Consuming skills should adopt the format from v1.0.0
> onward so the later transition requires no rework.

A skill that reads or writes ontology data declares its contract in a file
named `ontology-contract.yaml`, placed at the consuming skill's repo root
(alongside `.claude-plugin/plugin.json`).

## Purpose

The contract serves three goals:

1. Make explicit which types and relations a skill touches, so audits are
   straightforward.
2. Let ontology validate that the schema the consuming skill expects matches
   what is installed.
3. Surface conflicting expectations between skills before they corrupt the
   graph.

## Schema

```yaml
ontology_version: ~1.0.0           # required: which ontology version this contract targets
reads: [Type1, Type2, ...]         # required: types the skill reads
writes: [Type1, Type2, ...]        # required: types the skill writes
relations_read: [rel1, rel2]       # optional: relations the skill traverses
relations_write: [rel1, rel2]      # optional: relations the skill creates
domain_types: []                   # optional: type names the skill declares
preconditions: []                  # optional: invariants the skill assumes
postconditions: []                 # optional: invariants the skill guarantees
```

## Version constraints

The `ontology_version` field uses npm-style range syntax:

- `~1.0.0` — compatible with 1.0.x; equivalent to `>=1.0.0 <1.1.0`
- `^1.0.0` — compatible with 1.x.y; equivalent to `>=1.0.0 <2.0.0`
- `>=1.0.0 <2.0.0` — explicit range
- `1.0.0` — exact match

From v1.1.0 onward, ontology refuses to load a contract whose version is
unsatisfied by the installed schema.

## Domain type declarations

If `domain_types` is non-empty, the contract includes a `types:` block defining
each:

```yaml
domain_types: [CourtCase]

types:
  CourtCase:
    extends: Project              # must reference an existing core or domain type
    required: [case_number, court]
    properties:
      case_number: string
      court: string
      respondent: ref<Person>
```

Each domain type extends exactly one parent. Multiple inheritance is not
supported.

## Validation (v1.1.0+)

The reference implementation will validate contracts on skill activation:

```bash
ontology.py validate-contract /path/to/ontology-contract.yaml
```

Validation checks:

- The contract parses as valid YAML.
- All types in `reads`/`writes` exist in the core or in `types:`.
- All relations in `relations_read`/`relations_write` exist.
- Each `domain_types` entry has a matching `types:` block with a valid
  `extends`.
- `ontology_version` is satisfied by the installed schema.

Failed validation is reported as a warning; the consuming skill still loads,
but writes that violate the contract are rejected at write time.

## Pre- and postconditions

Pre- and postconditions are expressed as short statements. They are
documentation today; future versions may parse and enforce a subset.

```yaml
preconditions:
  - "Task.assignee must reference an existing Person"
  - "Project referenced in for_project must have status in [planning, active]"

postconditions:
  - "Created Task has status=open"
  - "Created Task is linked to exactly one Project"
```

## Example: minimal contract

```yaml
# ontology-contract.yaml
ontology_version: ~1.0.0
reads: [Task, Project]
writes: [Note]
```

## Example: contract with domain types

```yaml
# ontology-contract.yaml
ontology_version: ~1.0.0
reads: [Project, Person, Document]
writes: [CourtCase, Document]
relations_write: [has_owner, references]
domain_types: [CourtCase, LegalDeadline]

types:
  CourtCase:
    extends: Project
    required: [case_number, court]
    properties:
      case_number: string
      court: string

  LegalDeadline:
    extends: Task
    required: [statute_reference]
    properties:
      statute_reference: string
      irrevocable: boolean

preconditions:
  - "LegalDeadline.due must not be null"
postconditions:
  - "Created CourtCase is linked to exactly one Person via has_owner"
```
