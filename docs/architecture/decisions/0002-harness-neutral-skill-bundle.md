---
status: accepted
date: 2026-09-02
deciders: project owner
consulted: LyraResearch depersonalization pilot
informed: future contributors
---

# Harness-neutral skill bundle behind a marketplace

## Context and Problem Statement

The `skills/` component of `ue-toolchain` is not speculative work: it already exists as
18 skill bundles in the `LyraResearch` archive, grown from a line-by-line audit of a
first-party UE 5.6 sample. What is new is turning them into something a stranger can
install.

Two forces pull against each other.

**Distribution wants a vendor format.** Agent runners discover plugins through their own
manifest, in their own directory, with their own rules — component directories must sit
at the plugin root, and paths outside it are rejected. Writing to one such format is the
only way to get a one-command install today.

**The product must outlive that vendor.** The owner's constraint is explicit: *"не
привязывайся к клоду... инструмент должен нормально работать с любым харнесом или
агентом."* A skill that says "run this vendor command" is not portable content, it is a
script for one runner.

There is also a physical question. An agent runner copies the entire plugin root into its
cache on install. If the plugin root is the repository root, then the UE C++ plugin, the
MCP server and `examples/` are copied too — for a bundle whose actual payload is
Markdown. The precedent is measured: the VibeUE plugin copied into the reference project
weighs 161 MB.

## Decision Drivers

- **Content portability is a property of the files, not of the installer.** It has to be
  checkable, or it will rot on the first convenient exception.
- **One vendor adapter must not become the interface.** Adding a second harness must not
  require editing a single file under `skills/`.
- **The install surface should carry only what it delivers.** Source trees for the editor
  plugin and the MCP server are not part of a documentation bundle.
- **Discoverability without a runtime.** A harness that has never heard of any plugin
  format still needs to know what is in here and when to reach for each piece.

## Considered Options

1. **Whole repository is one plugin.** Vendor manifest at the repo root, `skills/` beside
   `Engine/` and `mcp-server/`.
2. **Separate repository for the skills.** Independent versioning and release cadence.
3. **Repository is a marketplace; the bundle is a subdirectory.**

## Decision Outcome

Chosen: **option 3**, with a neutral catalog inside the bundle.

```text
ue-toolchain/
├── .claude-plugin/marketplace.json     one adapter, points at the bundle
└── plugins/ue-design-skills/           the bundle, and the whole install surface
    ├── catalog.json                    source of truth: what is here, when to use it
    ├── .claude-plugin/plugin.json      the same adapter, one level down
    ├── skills/<name>/SKILL.md          plain Markdown + YAML frontmatter
    └── _gate/                          rules, poisoned fixtures, self-test
```

Three commitments follow:

**The catalog is the source of truth; the vendor manifest is an adapter.** `catalog.json`
lists every skill with `id`, `path`, `entry`, `description`, `use_when` and its
references. Any harness can read it, or ignore it and load the directory as context. A
second adapter is a new file beside the first, never an edit under `skills/`.

**Skill content names no harness.** Not the vendor, not its path variables, not its
command syntax. The rule holds for everything under `skills/`; the adapter directories are
exempt because being vendor-specific is their entire job.

**Both commitments are enforced, not documented.** They became gate rules P13 and P14 the
same hour the decision was made. A portability promise that lives only in an ADR is a
promise nobody checks.

### Consequences

- Good: the install surface holds only Markdown, JSON and the gate. C++ and examples stay
  out of the plugin cache.
- Good: skills release on their own cadence, before the editor plugin (phase 1) and the
  MCP server (phase 2) exist.
- Good: the neutrality claim is falsifiable — a single grep decides it.
- Bad: the layout is one level deeper than the component table in the handoff implies
  (`plugins/ue-design-skills/`, not `skills/`). The README is updated to match.
- Bad: two manifests describe the same bundle. They will drift unless the catalog stays
  authoritative and adapters are generated or reviewed against it.
- Neutral: nothing here prevents later extraction into its own repository. The bundle is
  self-contained by construction — the gate rejects any link that escapes a skill
  directory, so it moves with a `mv`. That was verified when it moved out of the archive.

## Confirmation

Checked at the time of writing, and required for every later change:

- `claude plugin validate . --strict` passes at the marketplace root and at the bundle
  root. *(passing)*
- `python _gate/gate.py .` reports zero violations on the bundle. *(passing, 14 rules)*
- `python _gate/test_gate.py` reports every rule reddening on its own poisoned fixture
  with a clean baseline. A rule that never reddens is treated as absent and fails the
  build. *(passing, 14/14)*
- No file under `skills/` matches the harness token list — vendor names, vendor path
  variables, vendor command syntax. *(P13)*
- Every skill directory has a catalog entry whose `path` holds a `SKILL.md`, and the
  catalog names no skill that is absent. *(P14, both directions)*
- Adding a second harness adapter changes no file under `skills/`. *(structural; re-check
  when the second adapter is written)*

## Deferred

- **Which second adapter comes first.** Not guessed. It will be written when a real
  harness needs it, and it will be the test of whether the catalog was actually enough.
- **License.** ~~Still open (handoff question 2). Deliberately *removed* from
  `catalog.json` and the vendor manifest rather than filled in with the planned value: a
  license asserted in shipped metadata before it is chosen is a claim with no author.~~
  **Resolved by [ADR-0003](0003-split-licensing-prose-and-code.md)**: prose CC BY-ND 4.0,
  code and metadata Apache-2.0, holder named. The original wording is kept struck through
  rather than deleted — the reason the field was left empty is part of how it was filled.
- **Whether the addressed audits are ever published.** For now the delivery carries
  detection recipes and stable entry identifiers; the source addresses stay in the
  research archive, where `_tools/resolve_id.py` resolves any identifier back to the file
  and line it came from.
