# ontology

Shared agent memory as a typed knowledge graph.

A local, structured notebook that AI agents read and write to so they remember
facts across sessions and across tools. Complementary to AI-native conversation
memory: native memory captures style and preferences, ontology captures facts.

## Install

```
/plugin marketplace add alfred-intelligence/claude-marketplace
/plugin install ontology@alfred
```

The reference implementation requires Python 3.10+ and PyYAML:

```
pip install pyyaml
```

## What it is

Every record is a typed entity with stable id, properties, and explicit
provenance. Entities link to one another through declared relations. The schema
is enforced on write. Storage is append-only JSONL in a directory owned by the
plugin (`${CLAUDE_PLUGIN_DATA}/`), so data persists across plugin updates and is
removed cleanly on uninstall.

The contract is documented in [SKILL.md](skills/ontology/SKILL.md). Other skills
declare their dependency on this skill and write to the same graph through the
documented schema.

## How it relates to AI memory

| | Native memory | Ontology |
|---|---|---|
| Form | Free-text summaries | Typed entities + relations |
| Location | AI provider's servers | Operator's filesystem |
| Audience | Single AI client | Any tool that knows the schema |
| Captures | Style, preferences, soft context | Hard facts about the operator's world |

The two layer. Use native memory for *how the operator works*; use ontology for
*what is true*.

## License

MIT. See [LICENSE](LICENSE).
