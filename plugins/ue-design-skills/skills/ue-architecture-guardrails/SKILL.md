---
name: ue-architecture-guardrails
description: >-
  Audit an Unreal Engine architecture for systemic failure modes across
  data-driven definitions, feature plugins, ability systems, input, UI,
  messaging, cosmetics and teams, settings and editor workflows. Use before
  adopting a modular architecture, at design review, before enabling runtime
  feature switching, during engine upgrades, or when indirect systems have
  become hard to debug. Provides ownership, lifecycle, context, validation,
  observability and integration-test gates.
---

# UE architecture guardrails

This skill is for **cross-system review**. It does not cover the implementation
of any one subsystem — each of those has its own skill and its own detection
recipes, and this one tells you which of them to run and in what order.

Systemic patterns and the go/no-go review: [patterns](references/patterns.md).
Fifteen cross-boundary failure modes: [failure modes](references/failure-modes.md).

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

The invariant behind all of it:

> Every systemic failure in a modular architecture lives **between** two
> subsystems that are each individually correct. That is why no subsystem's
> tests find it, and why review by subsystem cannot either.

---

## The seven invariants

A modular, data-driven architecture is healthy only when all seven hold:

1. **Justified abstraction** — every layer pays for real, named variability.
2. **Explicit ownership** — every dynamic resource has an owner, a receipt and
   an inverse.
3. **Symmetric lifecycle** — activate/deactivate and create/destroy are round
   trips, tested as round trips.
4. **Explicit context** — world, local player, authority and activation context
   are never inferred from globals.
5. **Compiled data graph** — semantic joins, references and bundles are
   validated by something that can fail a build.
6. **Observable indirection** — composition, blockers and listeners can be
   dumped at runtime.
7. **Cross-boundary tests** — lifecycle is tested across subsystem seams, not
   inside one manager.

**If a design review cannot show evidence for an invariant, treat it as absent.**
Not "probably fine" — absent. Every finding in the failure modes was in a
codebase where the invariant was assumed rather than demonstrated.

---

## 1. Abstraction pressure test

For each proposed layer, fill this in before writing code:

| Layer | Concrete variability #1 | #2 | Operations it removes | New lifecycle and tests it adds |
|---|---|---|---|---|

Reject or defer a layer when it has fewer than two real variants, when direct
code would be smaller and equally safe, when the project will not use dynamic
activation or a packaging boundary, or when the team cannot maintain the
validation and observability the layer requires.

**Do not adopt a large-studio architecture as an identity marker.** The cost is
paid per layer, per release, by whoever debugs it. Recipe: AG-01.

---

## 2. Ownership audit

Build a ledger for every dynamically added resource:

```text
resource · owner · scope · receipt · apply · revoke · sharing policy · rollback
```

Red flags, each of which has been observed in shipping code:

- a weak pointer presented as ownership;
- a global subsystem that "owns everything";
- cleanup that clears **all** resources rather than owned ones;
- a handle discarded immediately after registration;
- an owner that can die before the resource;
- two owners that can both remove one shared resource.

### The kill-owner test

Destroy each owner at the worst moment: during an async load, after apply but
before deactivation, after the target actor is gone, during map travel. Every
owned resource must disappear or transfer explicitly.

Subsystem recipes: `ue-modular-gameplay` MG-01 to MG-03,
`ue-input-architecture` IN-03, `ue-gas-architecture` GA-01. Recipe: AG-02.

---

## 3. Lifecycle as a transaction

```text
validate → load → activate 1..N → committed
failure at K → reverse K-1..1 → failed, with a reason
```

Three tests, all mandatory:

```text
baseline → activate → deactivate → baseline
baseline → activate → fail each step → baseline
baseline → activate → deactivate → reactivate → exactly one copy
```

The third is the one that finds duplicates, and it is the one nobody runs during
development, because in development you restart the editor instead. Recipe:
AG-03.

---

## 4. Context audit

For every mutable map and every subscription, ask which key is actually
required: process, game instance, world handle, activation context, local
player, actor, or net role. **A global key is valid only when the behaviour is
genuinely global.**

Required scenario matrix:

| Scenario | What it catches |
|---|---|
| multi-world editor play | process-global leaks |
| dedicated server + client | local-broadcast and presentation assumptions |
| listen server | double execution of local paths |
| two local players | UI, input and settings context leaks |
| map travel | stale listeners and state on long-lived scopes |

Recipes: AG-04, plus `ue-game-settings-architecture` GS-03 and
`ue-gameplay-messaging` MB-08.

---

## 5. Compile the data graph

Generate and validate the whole chain: production roots → identifiers →
references → plugin boundaries → bundles → semantic joins → leaf assets.

Failures that must fail a build, not a log line: unresolved identifiers, null
required fields, plugin dependency cycles, role-mismatched bundles, orphaned
producers or consumers of a semantic tag, prototype content under a production
root, an input tag with no granted consumer, a UI contribution with no matching
point, an incompatible payload family on a parent channel.

**Editor-only validation is feedback, not a gate.** Recipes: AG-05, plus
`ue-data-driven-architecture` DD-09 and DD-10.

---

## 6. Temporal dependency audit

Draw initialization prerequisites as a directed graph and reject: any cycle; a
prerequisite produced only by an optional or disabled path; an anonymous
next-tick delay; a generic "extension added" event used where semantic readiness
is required; a transition that can block with no diagnostic reason.

Then permute: feature activation before and after actor spawn, data before and
after possession, replication arrival order, contribution before and after its
point, listener before and after event. **Correct systems converge to the same
state.** Recipes: AG-06, plus `ue-modular-gameplay` MG-14 and MG-15.

---

## 7. Observability requirements

At minimum, expose read-only dumps for: the selected composition and its load
state; pending assets, plugins and actions with reasons; active feature plugins
and who requires them; per-actor readiness state and blockers; active input
contexts and semantic joins; granted capabilities by owner receipt; UI layers,
points and contributions with owners; message channels and listener counts;
authoritative identity and its mirrors; requested versus effective settings.

Logs need correlation fields: world, local player, actor, composition, plugin,
action, channel, owner.

**If diagnosis requires stepping through many assets with no state dump, the
indirection is operationally incomplete** — the architecture works and cannot be
supported. Recipe: AG-07.

---

## 8. The false-genericity test

For every public field or hook that implies behaviour — an ordering value, a
viewer parameter, an automatic mode, a removal function, a policy suffix:

1. find its consumer;
2. mutate the value in a fixture;
3. assert an observable delta;
4. test both the native and the scripting API where both are exposed.

No consumer and no delta means: implement it, remove it, or mark it
unsupported. **Never let a configurable no-op survive as stable API.**

This single test has the highest yield of anything in this skill. In the audited
material it independently found an ordering field that never sorts, a viewer
parameter that is ignored, an automatic quality pipeline with no caller, a
removal function with an empty body, and a composition part with no writer.
Recipe: AG-08, plus `ue-ui-architecture` UI-01, `ue-cosmetics-and-teams` CT-10,
`ue-game-settings-architecture` GS-06 to GS-08.

---

## 9. Event, state and command

Classify every interaction:

- **state** — a queryable authoritative model;
- **command** — one accountable service with a result and a failure;
- **event** — zero or many optional observers, a past-tense fact.

Red flags: UI reconstructing state from transient messages; a message asking an
unknown listener to perform required work; a local bus assumed to replicate;
presentation treated as authority. Recipes: AG-09, plus
`ue-gameplay-messaging` MB-12 to MB-14.

---

## 10. Version and adoption audit

Before copying any framework or sample, classify each element: architectural
invariant, sample scaffolding, project-specific behaviour, incomplete path,
confirmed defect, prototype content, version-sensitive API. Then pin the engine
version, the sample version, plugin versions and any serialized schema version,
and re-run behaviour probes after every upgrade.

**A current documentation page does not prove the content you copied is
current.** See `ue-reference-project-adoption` for the full classification and
its four tests. Recipe: AG-10.

---

## 11. Risk-based integration matrix

Do not attempt a Cartesian product. Require this spine:

1. standalone baseline;
2. dedicated server + remote client;
3. listen server;
4. two local players;
5. feature activates **before** receiver readiness;
6. feature activates **after** receiver readiness;
7. deactivate and reactivate;
8. actor destroyed before feature teardown;
9. late join;
10. map travel or composition change;
11. packaged clean client;
12. engine or plugin upgrade fixture.

**Every critical invariant needs at least one test crossing two subsystem
boundaries.** Unit tests inside one manager cannot find anything in this skill.

---

## 12. Severity triage

**Critical — stop feature work.** Ownership or rollback unknown; authority
duplicated; world or local-player context leaked; production data graph
unvalidated; persistent state reconstructed from messages; client presentation
affecting authority.

**High — fix before runtime switching or shipping.** Initialization cycle or
timing dependency; missing bundle with no fallback; native/scripting semantic
mismatch; undocumented ordering dependency; insufficient observability; version
mismatch.

**Medium — track with a bound.** Abstraction tax; linear scans acceptable at
current data size; editor-only gaps; duplicated scaffolding.

---

## 13. Go/no-go

- [ ] Every layer has two named variability pressures.
- [ ] Ownership ledger complete, kill-owner test passes.
- [ ] Lifecycle rollback and reactivation tests pass.
- [ ] Context matrix passes.
- [ ] Data graph validation runs where it can fail a build.
- [ ] Prerequisite graph acyclic and observable.
- [ ] State dumps and log correlation exist.
- [ ] Every public generic hook has a consumer test.
- [ ] Event, state and command classifications are correct.
- [ ] Replicated intent has a packaged-client realization test.
- [ ] Version set pinned.
- [ ] Cross-boundary matrix automated or scheduled.

**No-go rule: three unchecked Critical gates mean stop adding abstraction.**
Repair ownership, context and validation first — further indirection multiplies
the failure surface rather than the capability.

---

## Provenance

The systemic patterns and their severities come from a cross-system audit of
Epic's Lyra Starter Game on Unreal Engine 5.6 — the same audit that produced the
subsystem skills in this bundle. This skill exists because the same shapes
appeared in every subsystem: the individual findings are in those skills, and
what is here is the structure they share.

Source addresses stay in the research archive. Each entry carries a stable
identifier (`AG-01`, `AG-02`, …) resolving back to the audited material there.

## Evidence boundary

Cross-system conclusions from one project at one engine version, read as source
rather than run. Where a finding is a general principle rather than a measured
instance, the failure modes say so explicitly. The subsystem recipes referenced
above are the measured half; this skill is the ordering.
