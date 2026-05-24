# Schema migrations

> **Status in v1.0.0**: specification only. The `migrate` command and the
> `migrations/` directory are recognised by the reference implementation but
> not executed. The migration framework arrives in v2.0.0. The spec is
> documented here from v1.0.0 so future schema changes can be authored against
> a stable format.

Ontology data is append-only at the operation level, but schema definitions
evolve. Major schema-version changes require an explicit migration.

## When a migration is needed

- A required field is added to an existing type.
- A property is renamed or removed.
- An enum value is removed (existing data referencing it must be remapped).
- A relation is renamed or has its cardinality tightened.
- A type is removed (existing entities of that type must be relocated or
  deleted).

Additive changes (new optional field, new type, new relation) are
minor-version changes and do not require a migration.

## File layout

Each migration lives in `migrations/` and is named `NNNN-description.yaml`
where `NNNN` is a zero-padded sequence number:

```
migrations/
├── 0001-add-priority-to-task.yaml
├── 0002-rename-deadline-to-due.yaml
└── 0003-remove-attendee-shorthand.yaml
```

## File format

```yaml
from_version: 1.0.0
to_version: 1.1.0
description: "Add optional priority field to Task"

operations:
  - kind: add_property
    type: Task
    property: priority
    optional: true

  - kind: backfill
    type: Task
    property: priority
    value: normal
    where: { status: in_progress }
```

## Operation kinds

| Kind | Purpose |
|---|---|
| `add_type` | Declare a new entity type |
| `remove_type` | Remove a type; entities are deleted or relocated |
| `add_property` | Add a property to an existing type |
| `remove_property` | Remove a property; data is dropped |
| `rename_property` | Rename a property; data is preserved |
| `add_relation` | Declare a new relation |
| `remove_relation` | Remove a relation; existing edges are deleted |
| `rename_relation` | Rename a relation; existing edges are preserved |
| `backfill` | Set a property value for entities matching a filter |
| `remap_enum` | Replace one enum value with another for matching entities |

## Running migrations (v2.0.0+)

```bash
ontology.py migrate --to-version 1.1.0
```

The implementation applies all migrations whose `from_version` is at or above
the current `schema_version` and whose `to_version` is at or below the target,
in sequence-number order.

Each applied migration is recorded as a `Migration` entity in the graph so the
migration history is auditable from the data itself.

## Reversibility

Migrations are not required to be reversible. Operators who need a rollback
path should back up `graph.jsonl` before running a migration. The
implementation will prompt for confirmation before any non-additive migration
unless invoked with `--yes`.
