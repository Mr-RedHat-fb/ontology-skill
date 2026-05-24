#!/usr/bin/env python3
"""Reference implementation of the ontology contract.

See ../SKILL.md for the contract this implementation honours.

Requires Python >= 3.10 and PyYAML.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "error: PyYAML is required. Install with: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(2)


# ─── ULID ──────────────────────────────────────────────────────────────────

# Crockford base32 alphabet, used so ids stay sortable and human-readable.
_ULID_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _ulid() -> str:
    """Generate a 26-character ULID."""
    ts_ms = int(time.time() * 1000)
    payload = int.from_bytes(ts_ms.to_bytes(6, "big") + secrets.token_bytes(10), "big")
    chars = []
    for _ in range(26):
        chars.append(_ULID_ALPHABET[payload & 0x1F])
        payload >>= 5
    return "".join(reversed(chars))


# Short prefix per core type for human-readable ids.
_TYPE_PREFIX = {
    "Person": "person",
    "Organization": "org",
    "Project": "proj",
    "Task": "task",
    "Event": "event",
    "Location": "loc",
    "Document": "doc",
    "Note": "note",
    "Account": "account",
    "Device": "device",
}


def _id_for(entity_type: str) -> str:
    """Return a new id prefixed with the type's short tag."""
    prefix = _TYPE_PREFIX.get(entity_type, entity_type.lower())
    return f"{prefix}_{_ulid()}"


# ─── Storage ───────────────────────────────────────────────────────────────


def _data_root() -> Path:
    """Resolve the storage root, preferring the plugin data directory."""
    root = os.environ.get("CLAUDE_PLUGIN_DATA")
    if root:
        return Path(root)
    return Path.home() / ".local" / "share" / "ontology"


def _graph_path() -> Path:
    return _data_root() / "graph.jsonl"


def _schema_path() -> Path:
    return _data_root() / "schema.yaml"


def _ensure_storage() -> None:
    """Materialise the data root and seed the default schema on first run."""
    _data_root().mkdir(parents=True, exist_ok=True)
    if not _graph_path().exists():
        _graph_path().touch()
    if not _schema_path().exists():
        _schema_path().write_text(
            yaml.safe_dump(_default_schema(), sort_keys=False),
            encoding="utf-8",
        )


def _default_schema() -> dict:
    """The core schema, seeded on first run."""
    return {
        "schema_version": "1.0.0",
        "forbidden_property_names": [
            "password", "secret", "token", "api_key", "private_key",
            "ssn", "personnummer", "national_id",
        ],
        "types": {
            "Person": {"required": ["name"]},
            "Organization": {"required": ["name"]},
            "Project": {
                "required": ["name", "status"],
                "status_enum": [
                    "planning", "active", "paused", "completed", "abandoned",
                ],
            },
            "Task": {
                "required": ["title", "status"],
                "status_enum": [
                    "open", "in_progress", "blocked", "done", "cancelled",
                ],
            },
            "Event": {"required": ["title", "start"]},
            "Location": {"required": ["name"]},
            "Document": {"required": ["title"]},
            "Note": {"required": ["content"]},
            "Account": {"required": ["service"]},
            "Device": {
                "required": ["name", "kind"],
                "kind_enum": [
                    "laptop", "desktop", "phone", "server",
                    "vm", "container", "other",
                ],
            },
        },
        "relations": {
            "has_owner": {
                "from_types": ["Project", "Task", "Document"],
                "to_types": ["Person"],
                "cardinality": "many_to_one",
            },
            "member_of": {
                "from_types": ["Person"],
                "to_types": ["Organization"],
                "cardinality": "many_to_many",
            },
            "has_task": {
                "from_types": ["Project"],
                "to_types": ["Task"],
                "cardinality": "one_to_many",
            },
            "for_project": {
                "from_types": ["Task"],
                "to_types": ["Project"],
                "cardinality": "many_to_one",
            },
            "blocks": {
                "from_types": ["Task"],
                "to_types": ["Task"],
                "acyclic": True,
            },
            "for_event": {
                "from_types": ["Task"],
                "to_types": ["Event"],
                "cardinality": "many_to_one",
            },
            "attendee_of": {
                "from_types": ["Person"],
                "to_types": ["Event"],
                "cardinality": "many_to_many",
            },
            "at_location": {
                "from_types": ["Event", "Device"],
                "to_types": ["Location"],
                "cardinality": "many_to_one",
            },
            "references": {
                "from_types": ["Note"],
                "to_types": ["*"],
                "cardinality": "many_to_many",
            },
        },
    }


def _load_schema() -> dict:
    _ensure_storage()
    return yaml.safe_load(_schema_path().read_text(encoding="utf-8"))


def _append_op(op: dict) -> None:
    """Append a single operation to the graph log."""
    with _graph_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(op, ensure_ascii=False) + "\n")


def _read_ops():
    """Stream every operation from the graph log."""
    if not _graph_path().exists():
        return
    with _graph_path().open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _materialize() -> tuple[dict, list[dict]]:
    """Replay the log to obtain current entities and relations."""
    entities: dict = {}
    relations: list[dict] = []
    for op in _read_ops():
        kind = op["op"]
        if kind == "create":
            ent = op["entity"]
            entities[ent["id"]] = ent
        elif kind == "update":
            ent_id = op["id"]
            if ent_id in entities:
                entities[ent_id]["properties"].update(op["properties"])
                entities[ent_id]["updated"] = op["timestamp"]
        elif kind == "delete":
            entities.pop(op["id"], None)
            relations = [
                r for r in relations
                if r["from"] != op["id"] and r["to"] != op["id"]
            ]
        elif kind == "relate":
            relations.append({
                "from": op["from"],
                "rel": op["rel"],
                "to": op["to"],
                "provenance": op.get("provenance", {}),
                "created": op.get("timestamp"),
            })
        elif kind == "unrelate":
            relations = [
                r for r in relations
                if not (
                    r["from"] == op["from"]
                    and r["rel"] == op["rel"]
                    and r["to"] == op["to"]
                )
            ]
    return entities, relations


# ─── Validation ────────────────────────────────────────────────────────────


def _check_provenance(provenance: dict | None) -> list[str]:
    """Provenance must carry created_by and source_skill."""
    if not provenance:
        return ["provenance is required"]
    errs = []
    if not provenance.get("created_by"):
        errs.append("provenance.created_by is required")
    if not provenance.get("source_skill"):
        errs.append("provenance.source_skill is required")
    return errs


def _check_entity(entity: dict, schema: dict) -> list[str]:
    """Validate a single entity against the schema."""
    errs: list[str] = []
    etype = entity.get("type")
    if not etype:
        return ["entity is missing type"]
    type_def = schema.get("types", {}).get(etype)
    if type_def is None:
        return [f"unknown type: {etype}"]
    props = entity.get("properties") or {}

    for req in type_def.get("required", []):
        if req not in props:
            errs.append(f"{etype} missing required property: {req}")

    for key, value in props.items():
        enum_key = f"{key}_enum"
        if enum_key in type_def and value not in type_def[enum_key]:
            errs.append(
                f"{etype}.{key} value {value!r} not in {type_def[enum_key]}"
            )

    for forbidden in schema.get("forbidden_property_names", []):
        if forbidden in props:
            errs.append(f"{etype} contains forbidden property: {forbidden}")

    errs.extend(
        f"{etype}: {e}" for e in _check_provenance(entity.get("provenance"))
    )
    return errs


def _check_relation(rel: dict, entities: dict, schema: dict) -> list[str]:
    """Validate a relation against the schema and the current graph."""
    errs: list[str] = []
    rel_def = schema.get("relations", {}).get(rel["rel"])
    if rel_def is None:
        return [f"unknown relation: {rel['rel']}"]

    src = entities.get(rel["from"])
    dst = entities.get(rel["to"])
    if not src:
        errs.append(
            f"relation {rel['rel']}: from-entity {rel['from']} does not exist"
        )
    if not dst:
        errs.append(
            f"relation {rel['rel']}: to-entity {rel['to']} does not exist"
        )
    if not src or not dst:
        return errs

    from_types = rel_def.get("from_types", [])
    to_types = rel_def.get("to_types", [])
    if from_types != ["*"] and src["type"] not in from_types:
        errs.append(
            f"relation {rel['rel']}: from-type {src['type']} not in {from_types}"
        )
    if to_types != ["*"] and dst["type"] not in to_types:
        errs.append(
            f"relation {rel['rel']}: to-type {dst['type']} not in {to_types}"
        )
    return errs


def _check_acyclic(relations: list[dict], schema: dict) -> list[str]:
    """Detect cycles in any relation declared acyclic."""
    errs: list[str] = []
    for rel_name, rel_def in schema.get("relations", {}).items():
        if not rel_def.get("acyclic"):
            continue
        edges: dict[str, list[str]] = {}
        for rel in relations:
            if rel["rel"] == rel_name:
                edges.setdefault(rel["from"], []).append(rel["to"])
        white, gray, black = 0, 1, 2
        color: dict[str, int] = {node: white for node in edges}

        def visit(node: str) -> bool:
            color[node] = gray
            for nxt in edges.get(node, []):
                c = color.get(nxt, white)
                if c == gray:
                    return True
                if c == white and visit(nxt):
                    return True
            color[node] = black
            return False

        for node in list(color.keys()):
            if color[node] == white and visit(node):
                errs.append(f"cycle detected in acyclic relation {rel_name}")
                break
    return errs


def _check_cardinality(relations: list[dict], schema: dict) -> list[str]:
    """Enforce many_to_one cardinality."""
    errs: list[str] = []
    for rel_name, rel_def in schema.get("relations", {}).items():
        if rel_def.get("cardinality") != "many_to_one":
            continue
        seen: dict[str, str] = {}
        for rel in relations:
            if rel["rel"] != rel_name:
                continue
            existing = seen.get(rel["from"])
            if existing and existing != rel["to"]:
                errs.append(
                    f"relation {rel_name}: from {rel['from']} "
                    f"has multiple targets (cardinality many_to_one)"
                )
            seen[rel["from"]] = rel["to"]
    return errs


# ─── Commands ──────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _fail(errs: list[str]) -> None:
    for e in errs:
        print(f"error: {e}", file=sys.stderr)
    sys.exit(1)


def cmd_create(args: argparse.Namespace) -> None:
    schema = _load_schema()
    provenance = {
        "created_by": args.agent,
        "source_skill": args.skill,
    }
    if args.session_ref:
        provenance["session_ref"] = args.session_ref
    if args.external_id:
        provenance["external_id"] = args.external_id

    entity = {
        "id": _id_for(args.type),
        "type": args.type,
        "properties": json.loads(args.props),
        "provenance": provenance,
        "created": _now_iso(),
        "updated": _now_iso(),
    }
    errs = _check_entity(entity, schema)
    if errs:
        _fail(errs)
    _append_op({"op": "create", "entity": entity, "timestamp": entity["created"]})
    print(entity["id"])


def cmd_get(args: argparse.Namespace) -> None:
    entities, _ = _materialize()
    ent = entities.get(args.id)
    if not ent:
        _fail([f"entity not found: {args.id}"])
    print(json.dumps(ent, indent=2, ensure_ascii=False))


def cmd_list(args: argparse.Namespace) -> None:
    entities, _ = _materialize()
    out = [e for e in entities.values() if not args.type or e["type"] == args.type]
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_query(args: argparse.Namespace) -> None:
    entities, _ = _materialize()
    where = json.loads(args.where) if args.where else {}
    out = []
    for e in entities.values():
        if args.type and e["type"] != args.type:
            continue
        if all(e["properties"].get(k) == v for k, v in where.items()):
            out.append(e)
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_related(args: argparse.Namespace) -> None:
    _, relations = _materialize()
    out = [
        r for r in relations
        if r["from"] == args.id and (not args.rel or r["rel"] == args.rel)
    ]
    print(json.dumps(out, indent=2, ensure_ascii=False))


def cmd_relate(args: argparse.Namespace) -> None:
    schema = _load_schema()
    entities, relations = _materialize()
    candidate = {
        "from": args.from_id,
        "rel": args.rel,
        "to": args.to_id,
        "provenance": {"created_by": args.agent, "source_skill": args.skill},
    }
    errs = _check_relation(candidate, entities, schema)
    if not errs:
        tentative = relations + [candidate]
        errs.extend(_check_acyclic(tentative, schema))
        errs.extend(_check_cardinality(tentative, schema))
    if errs:
        _fail(errs)
    _append_op({
        "op": "relate",
        "from": candidate["from"],
        "rel": candidate["rel"],
        "to": candidate["to"],
        "provenance": candidate["provenance"],
        "timestamp": _now_iso(),
    })


def cmd_update(args: argparse.Namespace) -> None:
    schema = _load_schema()
    entities, _ = _materialize()
    ent = entities.get(args.id)
    if not ent:
        _fail([f"entity not found: {args.id}"])
    new_props = json.loads(args.props)
    merged = dict(ent["properties"])
    merged.update(new_props)
    tentative = dict(ent, properties=merged)
    errs = _check_entity(tentative, schema)
    if errs:
        _fail(errs)
    _append_op({
        "op": "update",
        "id": args.id,
        "properties": new_props,
        "provenance": {"created_by": args.agent, "source_skill": args.skill},
        "timestamp": _now_iso(),
    })


def cmd_delete(args: argparse.Namespace) -> None:
    entities, _ = _materialize()
    if args.id not in entities:
        _fail([f"entity not found: {args.id}"])
    _append_op({
        "op": "delete",
        "id": args.id,
        "provenance": {"created_by": args.agent, "source_skill": args.skill},
        "timestamp": _now_iso(),
    })


def cmd_validate(args: argparse.Namespace) -> None:
    schema = _load_schema()
    entities, relations = _materialize()
    errs: list[str] = []
    for e in entities.values():
        errs.extend(_check_entity(e, schema))
    for r in relations:
        errs.extend(_check_relation(r, entities, schema))
    errs.extend(_check_acyclic(relations, schema))
    errs.extend(_check_cardinality(relations, schema))
    if errs:
        for e in errs:
            print(f"validation error: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"ok: {len(entities)} entities, {len(relations)} relations")


def cmd_validate_contract(args: argparse.Namespace) -> None:
    print(
        "validate-contract is specification only in v1.0.0. "
        "See references/consumer-contract.md.",
        file=sys.stderr,
    )
    sys.exit(2)


def cmd_migrate(args: argparse.Namespace) -> None:
    print(
        "migrate is specification only in v1.0.0. "
        "See references/migrations.md.",
        file=sys.stderr,
    )
    sys.exit(2)


# ─── CLI ───────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="Ontology reference implementation")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create", help="Create a new entity")
    p.add_argument("--type", required=True)
    p.add_argument("--props", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--skill", required=True)
    p.add_argument("--session-ref")
    p.add_argument("--external-id")
    p.set_defaults(func=cmd_create)

    p = sub.add_parser("get", help="Fetch an entity by id")
    p.add_argument("--id", required=True)
    p.set_defaults(func=cmd_get)

    p = sub.add_parser("list", help="List entities, optionally by type")
    p.add_argument("--type")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("query", help="Filter entities by type and properties")
    p.add_argument("--type")
    p.add_argument("--where")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("related", help="List relations originating from an entity")
    p.add_argument("--id", required=True)
    p.add_argument("--rel")
    p.set_defaults(func=cmd_related)

    p = sub.add_parser("relate", help="Create a relation between two entities")
    p.add_argument("--from", dest="from_id", required=True)
    p.add_argument("--rel", required=True)
    p.add_argument("--to", dest="to_id", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--skill", required=True)
    p.set_defaults(func=cmd_relate)

    p = sub.add_parser("update", help="Patch an entity's properties")
    p.add_argument("--id", required=True)
    p.add_argument("--props", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--skill", required=True)
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("delete", help="Tombstone an entity")
    p.add_argument("--id", required=True)
    p.add_argument("--agent", required=True)
    p.add_argument("--skill", required=True)
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("validate", help="Validate the full graph")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser(
        "validate-contract",
        help="(v1.1.0+) Validate a consumer contract",
    )
    p.add_argument("path")
    p.set_defaults(func=cmd_validate_contract)

    p = sub.add_parser(
        "migrate",
        help="(v2.0.0+) Apply schema migrations",
    )
    p.add_argument("--to-version")
    p.set_defaults(func=cmd_migrate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
