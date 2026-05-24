# Core types

The core schema is small and stable. Anything more specific belongs in a domain
schema declared by a consuming skill.

This document describes what the core schema looks like in `schema.yaml`. The
reference implementation ships an equivalent schema as a default.

## Person

Someone the operator knows of: a contact, a colleague, a stakeholder.

```yaml
Person:
  required: [name]
  properties:
    name: string
    email: string?
    phone: string?
    role: string?       # how the operator relates to this person
    notes: string?
```

## Organization

A company, agency, school, or group.

```yaml
Organization:
  required: [name]
  properties:
    name: string
    kind: string?       # company, agency, school, community, other
    notes: string?
```

## Project

A piece of work the operator is engaged in. Endpoint-oriented; long-running
work belongs here.

```yaml
Project:
  required: [name, status]
  status_enum: [planning, active, paused, completed, abandoned]
  properties:
    name: string
    status: enum
    goals: string[]
    start: date?
    deadline: date?
    notes: string?
```

## Task

Something to be done, with a status. Lower granularity than a project.

```yaml
Task:
  required: [title, status]
  status_enum: [open, in_progress, blocked, done, cancelled]
  properties:
    title: string
    status: enum
    due: date?
    priority: enum?         # low, normal, high
    notes: string?
```

## Event

Something happening at a specific time.

```yaml
Event:
  required: [title, start]
  validate: "end >= start if end exists"
  properties:
    title: string
    start: datetime
    end: datetime?
    notes: string?
```

## Location

A place. Can be physical or virtual.

```yaml
Location:
  required: [name]
  properties:
    name: string
    address: string?
    coordinates: string?
    kind: enum?             # physical, virtual, hybrid
```

## Document

A file, URL, or document reference. Stores the reference, not the content.

```yaml
Document:
  required: [title]
  properties:
    title: string
    path: string?
    url: string?
    summary: string?
    media_type: string?
```

## Note

Freeform text the operator wanted remembered, with tags and references for
retrieval.

```yaml
Note:
  required: [content]
  properties:
    content: string
    tags: string[]
```

## Account

A service account or identity. Includes only the public surface; credentials
are stored elsewhere and referenced.

```yaml
Account:
  required: [service]
  properties:
    service: string
    username: string?
    profile_url: string?
    notes: string?
```

## Device

A physical or virtual machine known to the operator.

```yaml
Device:
  required: [name, kind]
  kind_enum: [laptop, desktop, phone, server, vm, container, other]
  properties:
    name: string
    kind: enum
    identifiers: string[]   # hostnames, MAC, serial, fingerprint
    notes: string?
```

## Core relations

Relations connect entities. The core ships with a minimal set; domain schemas
may add more.

```yaml
relations:
  has_owner:
    from_types: [Project, Task, Document]
    to_types: [Person]
    cardinality: many_to_one

  member_of:
    from_types: [Person]
    to_types: [Organization]
    cardinality: many_to_many

  has_task:
    from_types: [Project]
    to_types: [Task]
    cardinality: one_to_many

  for_project:
    from_types: [Task]
    to_types: [Project]
    cardinality: many_to_one

  blocks:
    from_types: [Task]
    to_types: [Task]
    acyclic: true

  for_event:
    from_types: [Task]
    to_types: [Event]
    cardinality: many_to_one

  attendee_of:
    from_types: [Person]
    to_types: [Event]
    cardinality: many_to_many

  at_location:
    from_types: [Event, Device]
    to_types: [Location]
    cardinality: many_to_one

  references:
    from_types: [Note]
    to_types: ["*"]           # any type — the literal star token
    cardinality: many_to_many
```

## Forbidden property names

Some property names are explicitly rejected across all types to prevent
foot-guns:

- `password`, `secret`, `token`, `api_key`, `private_key` — these must be
  stored elsewhere and referenced. Use `Account` for the public surface.
- `ssn`, `personnummer`, `national_id`, and similar government identifiers —
  out of scope for shared agent memory.

The reference implementation rejects writes whose properties include any of
these names.

## Provenance schema

Every entity and relation carries:

```yaml
provenance:
  required: [created_by, source_skill]
  properties:
    created_by: string        # agent identifier
    source_skill: string      # name@semver of the writing skill
    session_ref: string?      # optional opaque reference back to a session
    external_id: string?      # optional identifier in an external system
```
