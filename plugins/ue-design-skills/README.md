# ue-design-skills

Design-review skills for Unreal Engine 5.6 projects: norms for how to build a
system, plus reproducible recipes for finding the failures that never announce
themselves.

Every claim here came out of a line-by-line audit of a large first-party
reference project. What ships is not the audit — it is the recipe. See
[Provenance](#provenance).

## What is in the box

`catalog.json` is the index. It is plain JSON with no vendor vocabulary:

```json
{ "skills": [ { "id": "...", "entry": "skills/<id>/SKILL.md", "use_when": "..." } ] }
```

Each skill is a directory:

```text
skills/<skill-id>/
├── SKILL.md                      YAML frontmatter + normative body
└── references/
    ├── patterns.md               worked classification, measured scale, hygiene
    └── failure-modes.md          entries with a Detect recipe you can run
```

## Using it without any particular agent runtime

Nothing here needs a specific harness. Three ways in, cheapest first:

1. **Read it.** `SKILL.md` is Markdown. Open it.
2. **Load it as context.** Point your agent at `skills/<id>/` — the frontmatter
   `description` says when the skill applies, `use_when` in `catalog.json` says
   the same thing in one line for routing.
3. **Route on the catalog.** Parse `catalog.json`, match `use_when` against the
   task, load the matching `entry`.

Skill content is checked to contain no harness-specific tokens, so a recipe that
works for one agent works for the next. The manifest under `.claude-plugin/` is
one adapter over this catalog, not the source of truth; adding another adapter
does not touch `skills/`.

## Reading a failure-mode entry

Each entry carries six fields, in this order:

| Field | What it answers |
|---|---|
| **Mechanism** | what the code actually does |
| **Why it is silent** | why nothing crashes, logs or fails a test |
| **Why the obvious check misses it** | which natural search returns the wrong answer |
| **Symptom** | what a human reports, in their words |
| **Detect** | a command you run against your own tree |
| **Guardrail** | the rule that stops it recurring |

The three middle fields are the point. Anyone can write "check that fields have
writers"; only someone who did the work can say why `grep` answers "yes" when the
truth is "no".

## Detect recipes are meant to be run, not admired

Every recipe was executed against the reference project before shipping. That
caught two recipes which returned the wrong answer in exactly the case they were
written for — a member declared with an initializer matches every assignment
pattern you can write, and a character class containing `>` matches the `->`
operator. Both are documented in place, because the trap teaches more than the
command.

If a recipe returns nothing in your tree, widen it before concluding the problem
is absent. **An empty search result proves the pattern, not the absence.**

### They have also been run against the next engine version

Every runnable recipe -- 229 of them -- was executed against a second tree one
major version newer, and the two outputs compared line for line. Nothing was
one-sided: no recipe answered in one version and fell silent in the other. 176
matched exactly, 14 differed in size rather than in kind, and 39 returned nothing
in either tree.

Two cautions come with that, and they matter more than the numbers.

**Matching counts mean the search surface did not move, not that the claim still
holds.** Anything that depends on meaning -- who owns a fact, what replicates,
what is validated -- is not tested by counting lines.

**The comparison is worthless until the trees are made comparable.** In the first
pass 55 recipes appeared to differ; 41 of those differences were generated build
output present in one tree and a tooling plugin present in the other. One query
reported 122 files before the exclusions and 1 after. If you compare two versions
of anything this way, exclude build artefacts first and say that you did.

## What this bundle does not claim

- It is not a defect list for any current engine version. It is a worked example
  of a classification, measured once, on one version, in one workspace.
- Entries are evidence about *shapes*, not guarantees about your code.
- The delivery gate checks form — no absolute paths, no dangling links, no
  missing fields. It cannot check whether an entry is true.

## Provenance

The material comes from a research project that read Epic's Lyra Starter Game on
Unreal Engine 5.6 as source rather than running it. Source addresses stay in that
archive: an address in a tree you do not have is not actionable, and a recipe is.

Entry identifiers (`RA-01` and up) resolve to the audited locations in the
archive, so any specific claim can be produced on request.

## License

Copyright (c) 2026 MagentaDolphin. The prose is
[CC BY-ND 4.0](https://creativecommons.org/licenses/by-nd/4.0/); see
[LICENSE](LICENSE) for the exact boundary and the permissions that widen it.

In short:

| | |
|---|---|
| Read it, apply it, run the recipes on your code | yes, commercial work included |
| Edit it privately for your studio | yes, no permission needed |
| Redistribute it unchanged | yes, with attribution |
| Publish a modified version as your own product | no |
| Anything you build with it | yours, no claim made |

Four things are deliberately outside the NoDerivatives restriction, and all four
are Apache-2.0 or explicitly granted: `catalog.json` and
`.claude-plugin/plugin.json`, everything under `_gate/`, the shell commands
inside `Detect` fields, and format adapters and translations. The reasoning is
in `LICENSE` next to each grant — a bundle that tells you to verify every recipe
against your own tree cannot also forbid you to publish the correction.

### A request, not a condition

If these skills helped you ship something, a credit is welcome:

> ue-design-skills by MagentaDolphin

Nothing obliges you to give one. Attribution is required only when you
redistribute the material itself, and that requirement lives in the license
rather than here.
