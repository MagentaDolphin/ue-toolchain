---
name: ue-reference-project-adoption
description: >-
  Adopt architecture from an Unreal Engine reference or sample project (a
  first-party starter game, an engine template, an internal legacy title)
  without inheriting its shortcuts: classify each borrowed element as defect,
  showcase stub, deliberate sample-scope narrowing, architecture tax or
  foreign-product legacy, then decide copy/close/skip per element. Use when
  starting a project from a template, lifting a subsystem out of a sample,
  reviewing code that was copied from one, or explaining why a setting copied
  from the reference does nothing.
---

# UE reference project adoption

The invariant:

> A reference project shows you a **shape**, not a **contract**. Anything you copy
> without finding its consumer, its writer and its owner is a shape you now have to
> finish yourself.

Worked classification, tax analysis and vocabulary hygiene:
[patterns](references/patterns.md).
Nineteen detection recipes for silent failures:
[failure modes](references/failure-modes.md).

Read the failure modes before adopting or reviewing borrowed architecture. Each
entry names the mechanism, why it stays silent, why the obvious check misses it,
and a command you can run against your own tree.

Related skills: `ue-architecture-guardrails`, `ue-modular-gameplay`,
`ue-multiplayer-authority`, `ue-gameplay-tag-governance`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. The one thing that makes this hard

Broken code announces itself. It crashes, it logs, it fails a test.

An unfinished mechanism announces nothing. It returns a neutral value forever, and
that neutral value is indistinguishable from "the feature is off right now".

So the ranking that matters during adoption is **not severity**. It is *probability
of copying it without noticing*. Those are close to inverted: the most dangerous
elements in a mature sample project are the ones that never misbehave.

### Severity is not copyability

| | Pattern is safe to copy | Pattern is unsafe to copy |
|---|---|---|
| **Fails loudly** | plain defect — fix the line, keep the design | — |
| **Never fails** | foreign legacy — rename and keep | **stubs and scope narrowings** |
| **Works as intended** | tax you can afford | tax sized for someone else |

Only the bottom-right cell costs a subsystem rewrite instead of a line edit.

---

## 2. Five categories, and the decision each one implies

Classify every element you intend to borrow. The category, not the symptom,
determines what you do.

### C1 — Defect

A mistake the reference's authors would fix if they noticed.

**Decision:** fix the line; keep the surrounding design. A defect is not evidence
against the pattern that contains it.

### C2 — Showcase stub

Declared, editable, sometimes even read — but with no writer, no consumer, or a
hardcoded neutral result. Usually marked with a TODO, often not.

**Decision:** either implement it before exposing it, or delete the field. Never
ship an editable property whose consumer is a literal constant. Designers will
spend days tuning it.

### C3 — Deliberate sample-scope narrowing

The reference intentionally did not build a subsystem, because a sample does not
need it. Nothing is broken. The reference is internally consistent.

**Decision:** this is the expensive one. Decide explicitly, at adoption time,
whether your product needs the missing subsystem — and budget it. The failure mode
is not "we copied a bug", it is "we shipped without noticing there was a hole".

### C4 — Architecture tax

Correct, working, and sized for the reference author's team, release cadence and
platform matrix.

**Decision:** adopt by *need*, not by *completeness*. Copying an entire modular
stack because it is there means paying for an answer to a question you do not have.

### C5 — Foreign-product legacy

Constants, names and comments carried over from a different title.

**Decision:** rename on entry. Harmless as code, corrosive as vocabulary — in a
year, half the team will believe the foreign term is an engine concept.

---

## 3. Four tests, run before you copy anything

Cheapest first. Most stubs die at test 3.1.

### 3.1 Find the writer, not the reader

For any tunable field, search for **assignment**, not usage.

```bash
rg -n "\bMyField\b" Source/                 # declaration plus two reads: looks alive
rg -n "\bMyField\b\s*(=|\+=|-=)" Source/    # one hit, and it is the declaration
```

Watch the second line. A member declared as `float MyField = 0.f;` matches every
assignment pattern you can write, so the naive search answers "there is a writer"
in exactly the case where there is none. Subtract the declaration before you
conclude anything:

```bash
rg -n "\bMyField\b\s*(=|\+=|-=)" Source/ \
  | rg -v "\b(bool|u?int\d+|float|double|F[A-Z]\w+|T\w+<)\s+MyField\b"
```

A field that is read and compared but never written is worse than an unused field:
reading the code convinces you it is wired up. This is the single highest-yield
check in this skill — and, as the two commands above show, the one whose first
draft most often lies to you.

### 3.2 Find the comparison, not the plumbing

For any field named `Priority`, `Order`, `Weight`, `Rank`, `SortKey`: search for its
use inside a sort, predicate or comparison. Being passed through six functions and
stored in a struct means nothing.

If there is no comparison, the effective ordering is *registration order*, which in
a plugin-based project means *feature activation order* — non-deterministic from
the designer's point of view.

### 3.3 Ask who fills this in

Any of these is a stub or a narrowing until proven otherwise:

- an empty container next to a TODO;
- `const bool bSomething = false;` with the real expression in a comment;
- `const bool bIsValid = true;` consumed by a validation branch;
- a parameter threaded through several call layers that is never branched on;
- a function that exists, is public, and has zero callers in the codebase.

The distinction between C2 and C3 is only whether the author ever intended to fill
it in. Both cost you the same.

### 3.4 Ask what the adversary does

For anything on a trust boundary, ask: *what stops the other machine from lying
about this fact?* If the answer is "nothing", you are looking at C3, and the cost
of closing it is yours to price.

### 3.5 The paid test

When static reading is ambiguous, change the setting and measure whether anything
moves. Expensive, and the only test that cannot be fooled. Use a written protocol
with a restore point, one knob at a time.

---

## 4. Sample-scope narrowings a product must close

These are the holes that reference projects most commonly leave, in rough order of
how much they cost to close later:

| Narrowing | Why a sample omits it | What it costs a product |
|---|---|---|
| No lag compensation / server rewind | needs a real server, real latency, real test rig | Cannot be retrofitted cheaply — it dictates how abilities, tracing and damage are structured |
| Replication graph present but disabled | tuning it requires production-scale player counts | Traffic and CPU limits discovered in beta |
| No tag/asset redirect discipline | a sample never renames anything after release | Every rename becomes a breaking change with no migration path |
| Authority checks missing on state writers | single-process PIE never exercises the boundary | Silent state divergence, cheat surface |
| Fail-open defaults on unknown input | sample never produces unknown input | Security and gameplay decisions default to "allowed" |
| Preload/streaming machinery bypassed by config | sample content fits in memory | Hitching that looks like an engine bug |
| No teardown for dynamic additions | sample never unloads a feature | Leaks and duplicate registrations on the second load |

None of these is a bug report against the reference. Each is a line item in your
adoption budget.

### The rule

> Every C3 narrowing you accept must be written down as an accepted risk with an
> owner, or scheduled. "We did not notice" is the only unacceptable outcome.

---

## 5. Architecture tax: adopt need, not completeness

A reference project's modularity is an answer to a specific question — usually
"how do several teams ship seasonal content into one binary without merge
conflicts". If you do not have that question, you pay the cost and receive nothing.

Before adopting a modular stack, state the question it answers for *you*:

- more than one team shipping into the same binary?
- content added after launch without a client patch?
- game modes swapped at runtime by data?
- platform-specific feature sets?

Zero yes answers means the stack is tax. One or two means adopt the layers that
answer them and stop there.

### The C++/Blueprint boundary is also tax

A reference project's C++/BP split reflects its author's staffing. A codebase where
C++ exposes overwhelmingly *calls* rather than *override points* assumes a strong
C++ team is always available to extend it. Copy that boundary without that team and
designers hit a wall on their first non-trivial request.

Measure both sides before copying the ratio: how many `BlueprintCallable` entry
points versus how many `BlueprintImplementableEvent` and `BlueprintNativeEvent`
extension points, and who on your team can add to the second column. Measured
counts from one reference project are in [patterns](references/patterns.md).

### Measure the whole mount surface, not the primary content root

In a plugin-based project, plugins mount their own content roots. Any census,
budget or memory metric computed over the primary game root alone is wrong by
however much the plugins hold — in one measured reference, by roughly a factor of
six. Enumerate all mount roots, not just the obvious one.

---

## 6. Foreign legacy hygiene

On entry, rename:

- constants and type names carrying another product's brand;
- asset type identifiers whose names describe another game's content;
- comments copied from a different class;
- tags whose comment admits they are in the wrong namespace.

Do this at import time. After the first sprint it becomes archaeology, and the
foreign vocabulary starts appearing in design documents.

---

## 7. Fork and drift discipline

If you copy code rather than depend on a plugin:

1. Record the reference version and commit at import time, in a file next to the
   copy.
2. Keep imported code in a directory that is obviously imported.
3. Record every intentional divergence with a one-line reason.
4. Re-diff against the upstream on each engine upgrade; an unrecorded divergence is
   indistinguishable from an upstream fix you are about to lose.

Without this, engine upgrades turn every borrowed subsystem into a manual merge
with no ground truth.

---

## 8. Adoption procedure

For each subsystem you intend to borrow:

1. **Name the question** it answers for your product. If you cannot, stop.
2. **Read the consumer, not the declaration.** Confirm each field has a writer and
   each ordering field has a comparison.
3. **List the trust boundaries** it crosses and what validates each one.
4. **Classify every surprising element** as C1–C5.
5. **Decide per category:** fix / implement or delete / budget and schedule / trim
   to need / rename.
6. **Write down accepted C3 risks** with an owner.
7. **Record the import version** and directory.
8. **Add a test that would fail** if the narrowing you accepted became a bug.

---

## 9. Review checklist

- [ ] Every borrowed tunable field has a verified writer.
- [ ] Every ordering field participates in an actual comparison.
- [ ] No editable property is consumed by a hardcoded literal.
- [ ] Every parameter threaded through layers is branched on somewhere.
- [ ] Trust boundaries are enumerated; each has a named validator or an accepted
      risk.
- [ ] Missing subsystems (C3) are written down, not discovered later.
- [ ] Modular layers adopted map to a stated product need.
- [ ] C++/BP boundary matches the team that has to live with it.
- [ ] Metrics computed over all mount roots.
- [ ] Foreign-product vocabulary renamed at import.
- [ ] Import version and divergences recorded.
- [ ] Teardown exists for every dynamic addition adopted.

---

## 10. When copying wholesale is right

Adopt as-is, without this ceremony, when **all** of the following hold:

- the element is self-contained and has no trust boundary;
- you can name its consumer within one file;
- it has no editable tuning surface;
- replacing it later is a local edit, not a migration.

Small utilities, math helpers, container types and single-purpose components
qualify. Subsystems, lifecycle machinery and anything that touches replication,
persistence or the tag registry do not.

---

## 11. What this skill does not say

It does not say reference projects are bad guidance. A mature sample is the best
available evidence for *composition* — how definition and instance separate, how
readiness becomes an explicit chain, how presentation decouples from gameplay.

It says: the sample is evidence for the shape and silent about the finish. The
references exist so the silence is enumerated instead of discovered in production.

---

## Provenance

The classification, the four tests and every entry under `references/` come from a
line-by-line audit of Epic's Lyra Starter Game on Unreal Engine 5.6, read as source
rather than run. Source addresses stay in the research archive that produced this
skill; what ships is the detection recipe, because an address in someone else's
tree is not something you can act on and a recipe is.

Each entry carries a stable identifier (`RA-01`, `RA-02`, …) that resolves back to
the audited location in that archive. If you need the original address to settle a
dispute, it exists and can be produced.

## Evidence boundary

The measured material refers to one specific reference project on one engine
version in one workspace. It is a worked example of the classification, not a
defect list to carry into other engine versions or other samples. Re-run the four
tests against your own reference before trusting any specific claim.
