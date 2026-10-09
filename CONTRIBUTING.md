# Contributing

Thanks for reading this far. Two things are unusual about this repository, and both
change how a contribution is judged. Read them before opening a pull request.

## 1. Prose and code are licensed differently

| Path | License |
|---|---|
| `plugins/ue-design-skills/skills/**` and the bundle README | CC BY-ND 4.0 |
| `catalog.json`, `.claude-plugin/**`, `_gate/**`, Detect recipes | Apache-2.0 |
| Everything else in this repository | Apache-2.0 |

See [ADR-0003](docs/architecture/decisions/0003-split-licensing-prose-and-code.md) for
why, and `plugins/ue-design-skills/LICENSE` for the exact grants.

**NoDerivatives does not block contribution.** Publishing a fork in order to propose a
change back is explicitly permitted (additional permission 7). What it blocks is
publishing a modified version as a separate product.

### Inbound licensing

By opening a pull request you agree that your contribution may be distributed under the
license that already applies to the file you changed — CC BY-ND 4.0 for prose,
Apache-2.0 for code and metadata — and you confirm that you have the right to grant
this.

If your employer owns your work, get clearance before submitting. This matters more than
usual here: a bundle under NoDerivatives has to be able to state a single copyright
holder, and an unclear contribution is worse than a missing one.

## 2. A claim without a source you can point at is not a contribution

The whole bundle rests on one invariant, and it applies to changes as much as to the
original material:

> A skill that is confident and wrong is worse than a missing one.

Read `skills/ue-evidence-discipline/SKILL.md` first. It is short, and it is the standard
the review will use. In particular:

- **Every Detect recipe must have been run**, against a real tree, in both directions:
  it finds the known instance, and it stays quiet where there is none. A recipe that has
  not been run is a hypothesis. Say which tree you ran it against.
- **An empty search result proves the pattern, not the absence.** A negative claim must
  state the searches that produced it.
- **Measured, derived and open are never mixed in one sentence.**
- **Counts state their scope.** "94 definitions in 31 files across Source and Plugins" is
  a fact; "94 definitions" is a number waiting to be misused.

Corrections to existing entries are the most welcome kind of change, especially ones
that show a recipe failing. If you found a case where a recipe returns a false negative,
that is a finding, not a nuisance — the bundle documents three of its own.

## 3. Before you open the pull request

```bash
cd plugins/ue-design-skills
python _gate/gate.py .          # must print 0 violations
python _gate/test_gate.py       # must print all rules reddening on their fixtures
claude plugin validate . --strict
```

The gate is not advisory. It enforces, among other things: no absolute paths, no source
citations, no donor project name outside a Provenance section, no Cyrillic, no vendor or
harness name anywhere under `skills/`, no engine toolset, meta-tool or endpoint name
either (P17, see
[ADR-0004](docs/architecture/decisions/0004-engine-tool-surface-out-of-skill-content.md)),
and the six required fields on every failure-mode entry.

If you add a rule to the gate, **add a poisoned fixture that makes it fire.** The
self-test fails if any declared rule has no fixture. This is deliberate: the validator
this gate replaced ran green for months while checking a condition that could never
become true.

### Adding a failure-mode entry

Every entry carries six fields, in this order:

```
**Mechanism.**
**Why it is silent.**
**Why the obvious check misses it.**
**Symptom.**
**Detect.**
**Guardrail.**
```

Three of them — silence, why the obvious check misses it, and a Detect recipe that has
been run — cannot be written by someone who has not done the work. That is the point.
Entries missing any field are rejected by rule P09 before a human reads them.

Entry identifiers are sequential in document order (P15) and their prefix is unique
across skills (P16). If you insert an entry in the middle, renumber.

## 4. What is likely to be declined

- A recipe that has not been run, or whose output is not shown.
- An entry whose "why it is silent" restates the mechanism in other words.
- A skill that names a specific agent runtime, path variable or command syntax. The
  bundle must work with any harness; this is enforced by rule P13.
- Reformatting passes that touch many files without changing a claim.
- A new skill proposed before a discussion issue. Open the issue first — the bundle is
  deliberately small, and a sixteenth subsystem needs a reason.

## 5. Reporting something you cannot fix

Open an issue. A well-reported false negative in a Detect recipe is worth more than a
patch, because it usually means the recipe is wrong in a way the author could not see.

Include the tree you ran against (engine version is enough — no source needed), the
command, the output you got and the output you expected.
