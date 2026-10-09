# Failure modes: cross-system architecture

Ten failures that belong to **no single subsystem**, which is why each one
survived review of every subsystem it passes through.

The shared property here is different from the other documents in this bundle.
Elsewhere the mechanism is "a check exists and cannot fire". Here it is: **every
individual component is correct, and the defect lives in the seam.** Nobody owns
a seam. A reviewer of the messaging layer sees a correct bus; a reviewer of the
UI sees a correct widget; the failure is that the UI reconstructs state from the
bus, and that fact is written down nowhere.

That has a practical consequence for how these are detected. Most recipes below
are not a single search — they are a **join between two searches**, and the
finding is in the difference between the two result sets.

Where a mechanism is fully described by another skill, the entry says so and does
not restate it. Identifiers (`AG-01` and up) are stable and resolve back to the
audited material in the research archive.

---

## Abstraction

### AG-01 - A layer adopted for completeness rather than pressure

**Mechanism.** A modular architecture is copied whole from a reference project
because it is the reference's architecture, without asking which variability each
layer absorbs. Every layer is correctly implemented and paid for in full.

**Why it is silent.** Nothing fails. The cost is not a defect but a permanent tax:
every new mechanic now needs a class, a definition asset, a tag, an action, a
plugin, a validation rule and a UI extension. The team experiences this as "the
engine is like this".

**Why the obvious check misses it.** Review asks "is this implemented correctly?"
and the answer is yes at every layer. The question that finds it — "what are the
two concrete variants this layer separates?" — is not part of any code review,
because it is not about code.

**Symptom.** Feature velocity that falls as the project matures, with no single
slow component. Estimates that are consistently wrong in the same direction.

**Detect.** Count the axes against the variants they serve:

```bash
rg -c "class \w+ : public UGameFeatureAction" --glob "*.h" .   # action types
fd -e uasset -p "Experiences|GameFeature" | wc -l              # variants shipped
```

The finding is arithmetic, not textual: **planned variants fewer than
architectural axes.** In the audited reference, five feature plugins out of
eighty-one total carried the modular machinery — which pays for that project and
would not pay for a single-mode title.

**Guardrail.** For each layer, name two real variabilities it separates before
adopting it. If you cannot, defer the layer. See `ue-reference-project-adoption`
for the full classification and the adoption budget.

---

### AG-02 - Distributed control flow with no trace

**Mechanism.** A request travels definition → feature → action → extension event →
component → tag → message → widget. Each hop is decoupled by design.

**Why it is silent.** Decoupling is working exactly as intended. The absence of a
call stack is the feature, not a defect.

**Why the obvious check misses it.** A debugger shows one hop. Each hop's owner
can explain their hop. Nobody can explain the path, because reconstructing it
requires reading assets, config and code in three modules — and it has to be
reconstructed again next time.

**Symptom.** "Who triggered this?" costs an afternoon. Bugs reproduce reliably
while no class looks responsible. New engineers take months rather than weeks.

**Detect.** Test the property directly rather than searching for it: take a
recent bug and ask an engineer who did not write the feature to reconstruct the
path **from logs and dumps alone**, without opening assets. Then measure what
they needed and did not have.

Structurally, the precondition is visible:

```bash
rg -c "GetSubsystem<|BroadcastMessage|SendGameFrameworkComponentExtensionEvent" --glob "*.cpp" .
rg -c "UE_LOG.*Verbose.*(World|LocalPlayer|Experience|Feature)" --glob "*.cpp" .
```

A large first number with a small second is the finding: heavy indirection, no
correlated logging.

**Guardrail.** Structured lifecycle logs carrying world, player, experience,
plugin, action and owner identifiers; a generated composition graph; one index of
semantic tags and their consumers. Indirection without observability is not
architecture, it is a maze.

---

## Ownership and lifecycle

### AG-03 - Activation reviewed, deactivation assumed

**Mechanism.** Adding a component, a binding, a widget or a grant is easy and
visible. The inverse operation is written from memory, or not at all.

**Why it is silent.** Development restarts the editor instead of deactivating.
The happy path is exercised hundreds of times a day; the reverse path is
exercised by nobody until a player switches modes.

**Why the obvious check misses it.** Both functions usually exist and look
symmetric. The asymmetry is in what each enumerates — see `ue-modular-gameplay`
recipes MG-01 through MG-06 for the six distinct shapes this takes, each with its
own recipe.

**Symptom.** The second activation produces duplicates. Reported long after the
first, and usually attributed to the feature that was activated second.

**Detect.** The behavioural test is stronger than any search, and it is the one
gate this whole skill exists to insist on:

```text
baseline → activate → verify additions → deactivate → verify baseline
        → reactivate → verify exactly one copy
```

Run it with the actor existing before activation, spawned after activation, and
destroyed before deactivation.

**Guardrail.** An ownership ledger — resource, receipt, inverse — filled in
**before** implementation. A blank middle column is a rejected design, not a
follow-up task.

---

### AG-04 - A subsystem's lifetime mistaken for resource ownership

**Mechanism.** A long-lived subsystem holds registrations for resources owned by
short-lived objects. Weak references prevent crashes, so nothing appears wrong.

**Why it is silent.** Weak pointers do their job: the dead object is not called.
The **record** remains, and records are not visible in any profiler view that
answers "is this leaking?".

**Why the obvious check misses it.** The code is defensively written and looks
careful. Weak references read as evidence that ownership was considered — when
they are precisely the mechanism that lets the bookkeeping rot silently.

**Symptom.** Registration lists that grow across a session; cleanup that resorts
to clearing everything because per-owner removal was never possible; the same
resource removed twice by two owners.

**Detect.** For every registry, compare adds against removes and check the key:

```bash
rg -n "\.Add\(|\.Emplace\(|\.FindOrAdd\(" --glob "*.cpp" . | rg -i "listener|extension|handle|request"
rg -n "\.Remove\(|\.RemoveSwap\(|Unregister" --glob "*.cpp" . | rg -i "listener|extension|handle|request"
```

A registry with adds and no owner-keyed removal is the finding. A registry whose
only removal is a full clear is the same finding, one step later.

**Guardrail.** Every dynamic resource has exactly one named owner and one receipt.
Shared resources use reference counts or leases. "The subsystem owns it" is not an
answer; subsystems outlive the things they track.

---

## Context

### AG-05 - Global state where the scope is world or player

**Mechanism.** A registration, cache or setting is keyed globally, while the
things it describes belong to a world, a local player or an activation context.

**Why it is silent.** With one world and one player — the configuration in which
almost all testing happens — global and scoped are indistinguishable. The code is
correct in the case you run.

**Why the obvious check misses it.** The accessor reads naturally: a player asking
for its own settings, a subsystem holding its own registry. The scope error is one
line inside an accessor, or a missing key in a map declaration.

**Symptom.** Multi-world editor sessions cross-contaminate; split-screen players
share what should be per-player; a listen server processes an event twice. Each
appears as an unrelated bug in a different subsystem.

**Detect.** For every mutable registry, ask what the minimum sufficient key is,
then check what it actually is:

```bash
rg -n "TMap<.*>\s+\w+;" --glob "*.h" . | rg -v "FObjectKey|FGameFeatureStateChangeContext|ULocalPlayer"
rg -n -A4 "::Get\w*Settings\(\)" --glob "*.cpp" . | rg "::Get\(\)|GEngine->"
```

The second search is the specific case documented in
`ue-game-settings-architecture` GS-03: a per-player accessor returning a global
singleton, whose tell is a proliferation of "primary player only" conditions
elsewhere.

**Guardrail.** Key every mutable record by the minimum context that makes it
correct — activation context, world handle, local player where applicable. Then
run the required matrix: multi-world editor, dedicated server plus client, listen
server, two local players, map travel.

---

### AG-06 - Editor behaviour that differs from the shipped configuration

**Mechanism.** A branch keyed on running in the editor loads more, validates less,
or guesses identifiers that the packaged build resolves strictly.

**Why it is silent.** Both branches are correct for their environment. The editor
branch is usually more permissive, so everything works better where you are
looking.

**Why the obvious check misses it.** The branch is a single condition in a
subsystem nobody reads while working on a feature. Its consequences appear in
memory profiles, cook results and packaged-only failures — three places that are
each somebody else's job.

**Symptom.** Memory numbers that describe no shipping configuration. Features that
work in the editor and silently do nothing when packaged. Asset identifiers that
resolve in one and not the other.

**Detect.** Enumerate every editor divergence and judge each one deliberately:

```bash
rg -n "GIsEditor|WITH_EDITOR|IsRunningCommandlet|GIsPlayInEditorWorld" --glob "*.cpp" . -A3
rg -n "bShouldGuessTypeAndNameInEditor|PreloadInEditor|bOnlyCookProduction" Config/
```

In the audited reference this finds an editor branch that loads **both** role
bundles — which alone invalidates in-editor residency measurement — and a
configuration that guesses asset identifiers in the editor and not in the build.

**Guardrail.** Keep a written list of editor divergences and their justification.
Any measurement taken in the editor states which divergences apply to it.
See `ue-asset-loading-and-memory` AL-10.

---

## Data and validation

### AG-07 - A data graph with no compiler

**Mechanism.** Null references, wrong identifiers, cross-plugin cycles, prototype
content and semantic mismatches are all valid data. They load, they cook, they run.

**Why it is silent.** Data does not compile. There is no stage that can reject it
except one somebody chose to write — and that validation is typically
editor-only, so it does not run where it would matter.

**Why the obvious check misses it.** The validation *exists*, which satisfies the
question "is the data validated?". What it does not do is run in the build. In the
audited reference, eleven of twelve validation implementations were compiled out
of non-editor builds.

**Symptom.** A production playlist pointing at a test mode; a health pickup
granting a weapon definition; a missing bundle discovered only in a packaged
build.

**Detect.** Count validation, then count how much of it survives the build:

```bash
rg -c "IsDataValid" --glob "*.cpp" .
rg -n -B6 "IsDataValid" --glob "*.cpp" . | rg -c "WITH_EDITOR"
rg -n "class \w*ValidationCommandlet|UEditorValidatorBase" --glob "*.h" .
```

A ratio close to one, with no commandlet or automation path, means the data graph
is unvalidated where it ships. See `ue-data-driven-architecture` DD-09 and DD-10.

**Guardrail.** Run the same validation in automation that you run in the editor.
Add a production-root allow list so prototype paths cannot reach a shipped
playlist.

---

### AG-08 - A generic hook with no consumer

**Mechanism.** A public field or extension point is stored, copied and threaded
through an API — and never read by anything that changes behaviour.

**Why it is silent.** Every "is this used?" check answers yes, because the value
*is* used: passed, assigned, copied. What is missing is the comparison, the
branch, or the sort.

**Why the obvious check misses it.** This is the single most repeated shape in
this whole bundle, and it earns its own cross-system entry because it recurs in
every subsystem independently: an ordering field that never sorts, a viewer
identity that is ignored, a benchmark decision with no caller, a profile suffix
that is never populated, a removal function with an empty body, a flag written in
a constructor and never read.

**Symptom.** A designer configures a documented setting and observes no effect,
concludes their data is wrong, and works around it.

**Detect.** The general form — mentions minus comparisons:

```bash
F='Priority'
rg -c "\b$F\b" --glob "*.cpp" --glob "*.h" .                          # mentions
rg -n "\b$F\b\s*(<|>|<=|>=|==)|Sort.*\b$F\b|\b$F\b.*Sort" --glob "*.cpp" .
```

Mentions without comparisons is the finding. Per-subsystem instances have their
own recipes: `ue-ui-architecture` UI-01, `ue-cosmetics-and-teams` CT-10,
`ue-game-settings-architecture` GS-06 and GS-07, `ue-gas-architecture` GA-06,
`ue-modular-gameplay` MG-01.

**Guardrail.** Every public setting gets a consumer test: mutate it in a fixture,
assert an observable delta. Anything without one is implemented, removed, or
marked unsupported — never left as configurable decoration.

---

## Verification

### AG-09 - Single-process testing of a distributed property

**Mechanism.** A listen-server host shares memory with its client, so the
client/server split that produces a whole class of defects does not exist during
the test that would have caught it.

**Why it is silent.** The tests pass. They are real tests exercising real code;
they simply cannot express the failure.

**Why the obvious check misses it.** Coverage looks good and the feature demonstrably
works. The missing dimension is a **configuration**, not a code path, so no
coverage tool reports it.

**Symptom.** Features that ship having never run in the configuration they will
run in. Bugs that appear at first playtest and are attributed to the network layer.

**Detect.** This one is answered by an inventory rather than a search: list the
failure modes that require a separate process, and confirm each has a test in a
configuration that has one. From this bundle, the ones that cannot occur in a
single process include replicated-versus-validated confusion, call-site authority
guards, multicast used where state belongs, incomplete replicated-array callbacks,
readiness gates that assume a controller, and prediction with no correction path
(`ue-multiplayer-authority` NA-01, NA-04, NA-11, NA-13, NA-17, NA-19).

**Guardrail.** A dedicated server with two remote clients, one under latency and
packet loss, as the **minimum** configuration for accepting a networked feature.
Plus a mid-match joiner.

---

### AG-10 - A version set that drifts silently

**Mechanism.** Engine, reference sample and plugins evolve independently. Code
copied from a sample at one version keeps running against another.

**Why it is silent.** Compilation succeeds. Serialized fields still load. A stub
that changed behaviour between versions still returns something plausible.

**Why the obvious check misses it.** Documentation for the current version is
easy to find and describes the current version — not the vendored copy in the
project. Reading the docs actively produces false confidence.

**Symptom.** A method that "works differently now"; a structure size assertion
that fails after an upgrade; content that disagrees with the plugin that reads it.

**Detect.** Pin and verify rather than search. Where code manually enumerates the
members of an engine structure, a size assertion is the correct tripwire:

```bash
rg -n "static_assert\(sizeof\(" --glob "*.cpp" --glob "*.h" .
```

In the audited reference this appears five times against one engine structure. A
failing assertion after an upgrade is a **feature**: it means a new field would
otherwise have been silently ignored by five hand-written functions.

**Guardrail.** Pin the engine, sample and plugin versions. Keep compile-time
guards where you enumerate engine structures by hand. Re-run structural and
behavioural probes after every upgrade, and never treat a documentation page as
evidence about the code in your tree.
