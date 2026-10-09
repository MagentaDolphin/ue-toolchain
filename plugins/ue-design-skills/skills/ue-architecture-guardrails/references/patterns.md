# Patterns: reviewing an architecture across its seams

This is the cross-system half of the bundle. The other fifteen skills each audit
one subsystem; this one exists because the most expensive failures are not inside
a subsystem at all.

[Failure modes](failure-modes.md) carries the detection recipes. This file
carries the review procedure — what to ask, in what order, and what evidence to
demand before believing an answer.

---

## 1. Why seams are where the cost is

A subsystem has an owner. Someone can be asked whether the ability system is
correct, and they can answer.

A seam has no owner. "The UI reconstructs state from the message bus" is not a
fact about the UI or about the bus; it is a fact about their relationship, and
relationships do not appear in any file. Every finding in this skill was reviewed
— twice, once from each side — and survived.

That produces the review technique this whole document is built on:

> **Ask each question of the pair, not of the component.** Not "is this registry
> correct?" but "which context is this registry keyed by, and which context do its
> entries belong to?" The defect lives in the difference.

---

## 2. The seven invariants

An architecture of this kind is healthy only when all seven hold:

1. **Justified abstraction** — every layer pays for real variability.
2. **Explicit ownership** — every dynamic resource has an owner, a receipt and an
   inverse.
3. **Symmetric lifecycle** — activate/deactivate and create/destroy are round
   trips, tested as round trips.
4. **Explicit context** — world, local player, authority and activation context
   are never inferred from globals.
5. **Compiled data graph** — semantic joins, references and bundles are validated
   somewhere that runs in the build.
6. **Observable indirection** — composition, blockers and listeners can be dumped.
7. **Cross-boundary tests** — lifecycle is tested across subsystem seams.

**If a review cannot produce evidence for an invariant, record it as absent.** Not
"probably fine" — absent. Every finding in the audit that produced this skill was
in a system whose author would have said it was fine.

---

## 3. Abstraction pressure test

Fill this before adopting a layer, not after:

| Layer | Variability #1 | Variability #2 | Operations removed | Lifecycle and tests added |
|---|---|---|---|---|
| feature plugin | | | | |
| experience / mode definition | | | | |
| semantic input | | | | |
| UI extension points | | | | |
| message bus | | | | |

Defer a layer when it has fewer than two real variants or owners; when direct code
would be smaller and equally safe; when the project will not use dynamic
activation or a packaging boundary; or when the team cannot maintain the
validation and observability the layer requires.

**The arithmetic that decides it:** planned variants versus architectural axes. If
axes exceed variants, the architecture is aspirational. Recipe: AG-01.

---

## 4. The ownership ledger

For every dynamically added resource:

```text
resource
owner
scope        process / game instance / world / local player / actor
receipt      the handle that proves this owner added it
apply        the call that adds
revoke       the call that removes exactly this
sharing      what happens when two owners want the same resource
rollback     what happens if apply fails halfway
```

Red flags, each seen in the audited reference:

- a weak reference presented as ownership;
- a global subsystem that "owns everything";
- cleanup that clears all resources rather than owned ones;
- a handle discarded at the moment it is returned;
- an owner that can die before its resource;
- two owners able to remove the same shared resource.

### The kill-owner test

For each owner, destroy it at the worst moment: during an async load, after apply
but before normal deactivation, after the target actor is destroyed, and during
map travel. Every owned resource must disappear or transfer explicitly.

This is a cheap test that finds expensive defects, and almost nobody runs it.

---

## 5. Lifecycle as a transaction

```text
validate → load → activate 1..N → committed

failure at step K
    → reverse K-1 .. 1
    → failed, with a reason that names the step
```

Three mandatory sequences:

```text
baseline → activate → deactivate → baseline
baseline → activate → fail each step in turn → baseline
baseline → activate → deactivate → reactivate → exactly one copy
```

The third is the one that finds duplicates, and the one development never runs
because development restarts the editor instead. Recipe: AG-03.

---

## 6. Context audit

For every mutable map or subscription, ask which key is **required**: process,
game instance, world handle, activation context, local player, actor, or net role.

A global key is correct only when the behaviour is genuinely global. The
temptation is that a global key is simpler and, with one world and one player,
indistinguishable.

### The required matrix

| Scenario | What it catches |
|---|---|
| multi-world editor session | process-global leaks |
| dedicated server plus remote client | local-broadcast and presentation assumptions |
| listen server | doubled local paths |
| two local players | UI, input and settings context leaks |
| map travel | stale listeners surviving a world |

Recipes: AG-05, AG-06.

---

## 7. The data graph needs a compiler

Generate and validate the path from production roots through identifiers,
references, plugin boundaries, bundles and semantic joins to leaf assets.

Fail the build on: unresolved identifiers or soft references; null required
fields; plugin dependency cycles; role-bundle mismatches; orphan producers or
consumers of a semantic tag; prototype or test paths reachable from a production
root; an input tag with no granted consumer; a UI extension with no point or
contract; an incompatible payload family under a parent channel.

**The crucial property is where it runs.** Editor-only validation is useful
feedback and is not a safety boundary. Recipe: AG-07.

---

## 8. Temporal dependencies

Draw initialization prerequisites as a directed graph — each feature state and
what it requires. Reject: cycles; a prerequisite produced only by an optional or
disabled path; an anonymous next-tick delay; a generic "extension added" event
used where semantic readiness is meant; a blocked transition with no diagnostic.

### Permutation test

Vary activation before and after actor spawn, archetype data before and after
possession, replication arrival order, UI point before and after extension, and
listener before and after event. **Correct systems converge to the same state
from every order.** Systems that pass by luck have one order that works.

---

## 9. Observability is a requirement, not tooling polish

Expose read-only dumps for: the selected mode and its load state; pending assets,
plugins and actions **with reasons**; active feature plugins and who requires
them; per-feature actor readiness and blockers; active input contexts and their
semantic joins; granted capabilities by owner receipt; UI layers, points,
extensions and owners; message channels with listener counts and owners; the
authoritative team identifier and its mirrors; requested versus effective
settings with clamps.

Logs carry correlation fields: world, local player, actor, experience, plugin,
action, channel, owner.

**The acceptance test:** an engineer who did not build the feature diagnoses an
injected failure from logs and dumps alone, without opening assets, within a
bounded time. If that is impossible, the indirection is operationally incomplete
regardless of how clean the code is. Recipe: AG-02.

One thing worth stealing outright: the audited reference ships console variables
that inject artificial delay into mode loading. A reproducible way to exercise
slow-load, timeout and cancellation paths is worth more than it costs, and almost
nobody builds one.

---

## 10. The false-genericity sweep

For every public field or hook implying behaviour — an ordering value, a viewer
identity, an automatic-benchmark decision, a removal function, a profile suffix,
a policy flag:

1. find its consumer;
2. mutate the value in a fixture;
3. assert an observable delta;
4. test both native and visual-script surfaces where exposed.

No consumer or no delta means: implement it, remove it, or mark it explicitly
unsupported. Never let a configurable no-op survive as stable API.

This sweep is worth running as a scheduled activity rather than a review step,
because the shape recurs independently in every subsystem. Recipe: AG-08.

---

## 11. Event, state and command

Classify every interaction:

- **state** — a queryable authoritative model;
- **command** — one accountable handler, with a result and a failure;
- **event** — a past-tense fact with zero or many optional observers.

Red flags: UI reconstructing state from transient messages; a message asking an
unknown listener to perform required work; a local bus assumed to replicate;
presentation treated as authority.

The test that settles it: **if a listener subscribes one second late, must it know
the current value?** Yes means state. No means an event is acceptable.

---

## 12. Version and adoption

Before copying from a reference, classify each element: architectural invariant
(adopt), sample scaffolding (replace), project-specific behaviour (evaluate),
unfinished path (do not claim supported), confirmed defect (fix with a regression
test), prototype content (exclude from production), version-sensitive API (verify
live).

Pin the engine version and changelist, the sample version, plugin versions, and
any serialized schema version. Re-run probes after every upgrade.

**A current documentation page is not evidence about the code in your tree.**
Recipe: AG-10. The full classification is `ue-reference-project-adoption`.

---

## 13. The integration matrix

Do not attempt the full product of configurations. Require this spine:

1. standalone baseline;
2. dedicated server plus remote client;
3. listen server;
4. two local players;
5. feature activates **before** receiver readiness;
6. feature activates **after** receiver readiness;
7. deactivate and reactivate;
8. actor destroyed before feature teardown;
9. late join;
10. map travel or mode change;
11. packaged clean client;
12. engine or plugin upgrade fixture.

Every critical invariant needs at least one test crossing **two** subsystem
boundaries. Unit tests inside one manager cannot express these failures.
Recipe: AG-09.

---

## 14. Triage

**Critical — stop feature work.** Resource ownership or rollback unknown;
authority duplicated; world or player context leaking; production data graph
unvalidated; persistent state reconstructed from messages; client presentation
affecting authority.

**High — fix before runtime switching or shipping.** Initialization cycles or
timing dependencies; missing packaged-asset fallback; native and visual-script
semantics diverging; undocumented ordering dependencies; insufficient
observability; version mismatch.

**Medium — track with a bound.** Abstraction tax; linear scans acceptable at
current data size; editor-only polish gaps; duplicated sample scaffolding.

### The no-go rule

Three unchecked Critical gates mean **stop adding abstraction and features**.
Repair ownership, context and validation first. More indirection on an
unvalidated base multiplies the failure surface rather than organising it.

---

## Provenance

The invariants and gates here are generalized from a full-project audit of Epic's
Lyra Starter Game on Unreal Engine 5.6 — its data-driven layer, feature plugins,
ability system, input, UI, messaging, cosmetics and teams, settings, loading and
streaming — read as source and configuration rather than run.

Every cross-system failure mode in [failure modes](failure-modes.md) was observed
in that project, in a subsystem whose local implementation was correct. That is
the reason this skill exists as a separate document rather than as a section in
each of the others.

Source addresses stay in the research archive that produced this skill. Entry
identifiers resolve back to the audited locations, so any specific claim can be
produced on request.

## Evidence boundary

One project, one engine version, one workspace. The invariants are transferable;
the specific instances are evidence, not guarantees about other versions. Re-run
the detection recipes against your own tree before acting on any specific claim.
