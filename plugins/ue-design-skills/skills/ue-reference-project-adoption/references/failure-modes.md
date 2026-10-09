# Failure modes when adopting a reference project

Nineteen ways a borrowed subsystem stays quiet while doing nothing.

They share one property: **each is discovered late by construction.** Every entry
here compiles, passes review, produces no warning and no log line. What is absent
is a writer, a comparison, a validator or an owner — and absence does not raise.

Each entry gives you a `Detect` you can run against your own tree today. The
recipes are deliberately crude: a grep that returns nothing where reads exist is
worth more than a subtle static analysis nobody runs.

`RA-nn` identifiers are stable and resolve to the audited location in the research
archive behind this skill.

Categories: **C1** defect · **C2** showcase stub · **C3** deliberate sample-scope
narrowing. Architecture tax (C4) and foreign vocabulary (C5) are not failure modes
and live in [patterns](patterns.md).

---

## C1 — Defects

Fix the line, keep the design. A defect is not evidence against the pattern that
contains it.

### RA-01 - Tag picker filtered to a namespace that does not exist

**Mechanism.** An editable gameplay-tag property carries a
`meta = (Categories = "Some.Root")` filter, and no tag in the project is declared
under that root. The real tags live under a different prefix.

**Why it is silent.** The filter's only job is to narrow an editor dropdown. A
filter that matches nothing produces an empty dropdown, which is visually identical
to "no tags of this kind have been authored yet". Nothing compiles differently,
nothing logs, and the property simply stays unset forever.

**Why the obvious check misses it.** The filter string is syntactically valid and
the property is genuinely declared, read and used — every "is this wired up?" search
answers yes. Nobody searches for the *filter value* as a tag prefix, because it
reads like a category label rather than a key that has to resolve. In the measured
reference this was one of only fourteen places in the entire project where tag input
was constrained at all, so the one guardrail present was also the one misconfigured.

**Symptom.** A designer opens the dropdown, sees nothing, concludes the feature is
unimplemented, and leaves the field empty. The system then behaves as if the
designer chose "none".

**Detect.** Extract every filter value and confirm each resolves to declared tags:

```bash
rg -o 'Categories\s*=\s*"([^"]*)"' -r '$1' Source/ Plugins/ | sort -u
# then, per root R:
rg -c "\"R\." Config/*.ini Source/
```

A root with zero declarations is a dead filter.

**Guardrail.** A `Categories` filter is a guardrail only if something proves it
resolves. Add a startup or CI assertion that every filter value matches at least one
declared tag; an empty picker must be an error, not a shrug.

---

### RA-02 - A misspelling that works because every side repeats it

**Mechanism.** A tag or string key is misspelled in its declaration and in every
consumer. The string is the join between config, code and platform overrides, so
identical errors on both sides join correctly.

**Why it is silent.** Correctness for a string join means *all sides agree*, not
*the string is a word*. Six identical misspellings across four files function
exactly as six correct ones would. There is no side that could disagree.

**Why the obvious check misses it.** Searching for the correct spelling returns
nothing, and an empty result reads as "this feature is not implemented here" rather
than "it is spelled differently". The compiler never sees the literal as a name, and
spell-checkers do not run over identifiers. The bug only becomes visible at the
moment someone *fixes* it at one site.

**Symptom.** Nothing at all — until a cleanup pass corrects the spelling in one
file. The join then breaks with no error, and the regression is attributed to
whatever else shipped that week.

**Detect.** Find tag literals repeated as raw strings instead of referenced through
one constant:

```bash
rg -oN '"[A-Za-z][A-Za-z0-9]*(\.[A-Za-z][A-Za-z0-9]*){2,}"' Source/ Config/ \
  | sort | uniq -c | sort -rn | head -40
```

Any literal appearing more than once is a join with no single source of truth.

**Guardrail.** One declaration site per tag; every other site references the
constant. Then a rename is a compile error instead of a silent disconnection.

---

### RA-03 - A loop over a container that has no producer

**Mechanism.** A local container is declared next to a TODO explaining how it will
one day be filled, then iterated immediately. Nothing ever fills it.

**Why it is silent.** Zero iterations is a legal, successful outcome. The function
returns normally and reports success, because doing nothing to an empty set is
indistinguishable from doing the work correctly.

**Why the obvious check misses it.** The code reads as a complete mechanism:
declaration, loop, and a body that does real work. Review attention goes to whether
the body is correct. The missing piece is one level up — the container has a
consumer and no producer, and reviewers check consumers.

**Symptom.** A documented behaviour ("these entries are always loaded") reports zero
at runtime, and is diagnosed as a content or configuration problem for days.

**Detect.** For every container that is iterated, look for a writer:

```bash
rg -n "for\s*\(.*:\s*(\w+)\)" -r '$1' Source/ | sort -u > /tmp/iterated
# per name N:
rg -n "\bN\b\s*\.\s*(Add|Append|Emplace|Push|Insert|Reserve)" Source/
```

Reads without writes mean the loop is decoration.

**Guardrail.** Do not ship a loop over a container that has no producer in the same
translation unit or an obvious injection point. If the producer is future work, the
loop is future work too.

---

### RA-04 - Progress arithmetic with inverted operands

**Mechanism.** A startup progress fraction computes each sub-step's contribution
with the operands the wrong way round, so the reported value does not advance while
a single long step runs.

**Why it is silent.** The result stays inside the valid range and still increases
across step boundaries. It is a wrong number, not an invalid one, so no assertion
and no clamp fires.

**Why the obvious check misses it.** On a developer machine with a warm cache the
whole sequence finishes in under a second, and nobody watches one step long enough
to see it stall. The code is exercised on every launch and observed on none.

**Symptom.** On a cold shader cache or a slow disk the bar freezes for a long time
and players report a hang. The engineering response is to look for a deadlock,
because the bar is trusted.

**Detect.** Two options. Force the slow path with whatever artificial-delay cvar the
loading system provides and watch whether the value moves within a step. Or unit-test
the progress function directly: feed it a fixed step count and assert the value is
strictly increasing at every sub-step, not just at step boundaries.

**Guardrail.** Progress arithmetic gets a test. It is the canonical example of code
that runs constantly and is observed only under conditions developers do not have.

---

### RA-05 - Listener removed using the wrong channel key

**Mechanism.** A tag-addressed pub/sub subsystem walks parent tags when
broadcasting. On finding an expired listener it removes the handle using the
*original broadcast channel* rather than the ancestor tag currently being visited.
Handle identifiers are unique only within a channel.

**Why it is silent.** Both outcomes are legal operations on a map. Either the key is
absent and removal is a no-op — the stale listener survives in the parent bucket — or
a different listener happens to hold the same channel-local id and is removed from
the wrong bucket. Neither path raises.

**Why the obvious check misses it.** The removal call is present, correctly typed,
and looks right. The defect is in *which key* is passed, and both candidate keys are
in scope, same-typed, and similarly named. Type checking cannot separate them, and
review reads the statement as "remove the expired listener".

**Symptom.** A listener that was unregistered keeps receiving messages, or an
unrelated listener silently stops receiving them. The failure surfaces in whichever
system owned the collateral listener, arbitrarily far from the subsystem at fault.

**Detect.** Inside any parent-tag or hierarchy traversal, confirm every mutation
keys on the loop cursor rather than the function parameter:

```bash
rg -n -B12 "(Unregister|Remove\w*Listener|RemoveAt)" Source/ \
  | rg -n "for\s*\(|ParentTag|Ancestor"
```

Then read each hit and check the key.

**Guardrail.** Make listener identity an explicit pair type — channel plus id — so
passing the wrong channel fails to compile instead of silently mis-keying.

---

## C2 — Showcase stubs

The defining property: **the declaration and the consumer both exist; the writer
does not** — or the consumer is a literal. Neither a compiler warning nor an
"unused symbol" search finds these.

### RA-06 - Editable tunable with a live reader and no writer

**Mechanism.** A designer-facing cooldown is compared against a "last event"
timestamp field. The timestamp is declared and read, and is never assigned anywhere
in the codebase.

**Why it is silent.** Time elapsed since an unset timestamp is time since world
start, which always exceeds any sane threshold. The comparison is permanently true,
so the gate the setting was meant to impose never rejects anything. Permanently
allowing is a valid runtime state, so nothing errors.

**Why the obvious check misses it.** The field is read twice and participates in a
comparison, so every "is this used?" heuristic — grep, IDE find-usages, unused-symbol
warnings — answers yes. What is missing is the **writer**, not the reader, and no
default tool asks that question. This is the highest-yield check in the whole skill
precisely because it inverts the usual direction of the search.

**Symptom.** A designer tunes the value for days, reports it has no effect, and is
told to check their data. The setting is then either abandoned or "fixed" by
changing something else that happens to correlate.

**Detect.** For every `EditAnywhere` or `EditDefaultsOnly` numeric property and for
every timestamp it is compared against, search for an assignment rather than a
mention:

```bash
rg -n "\bLastFireTime\b" Source/                 # reads: several
rg -n "\bLastFireTime\b\s*(=|\+=|-=)" Source/    # one hit - and it is the declaration
```

The second search does **not** come back empty, and that is the trap. A member
declared with an initializer (`double LastFireTime = 0.0;`) matches every
assignment pattern you can write, so the naive search reports a writer that does
not exist. Subtract the declaration before concluding:

```bash
rg -n "\bLastFireTime\b\s*(=|\+=|-=)" Source/ \
  | rg -v "\b(bool|u?int\d+|float|double|F[A-Z]\w+|T\w+<)\s+LastFireTime\b"
```

Empty after that subtraction, with live reads elsewhere, is a stub. Verified on
the reference: the unsubtracted search returns one line, the subtracted search
returns none.

**Guardrail.** Never ship an editor-exposed property whose value has no writer.
Every tunable needs one owning assignment site and one test that moves the value and
asserts an observable delta.

---

### RA-07 - Ordering field that is stored, copied and never compared

**Mechanism.** A `Priority` integer is accepted by eight registration overloads,
stored on the entry, copied into the request struct, and never appears in a sort, a
predicate or a comparison anywhere.

**Why it is silent.** The field has a defined value at all times and travels
correctly through the entire API. Ordering still happens — it is just registration
order. A plausible order is produced on every run, so nothing looks wrong.

**Why the obvious check misses it.** The value is written, read, copied and passed
across a large public surface. Usage counts are high. Any review that asks "is
`Priority` used?" finds a dozen sites and stops. The right question is narrower: does
it appear inside a `Sort`, `<`, `>` or predicate? That question is not one anyone
thinks to ask about a field that is obviously plumbed.

**Symptom.** Widget or handler order changes between runs and between machines. In a
plugin-based project, registration order is feature activation order, so the symptom
reads as a race condition and gets chased in the wrong subsystem.

**Detect.** Search for the comparison, not the plumbing:

```bash
F='(Priority|Order|Weight|Rank|SortKey)'
rg -n "\b$F\b" Source/ Plugins/ | wc -l                    # plumbing: many
rg -n "(Sort|StableSort|Algo::)" Source/ Plugins/ | rg "\b$F\b"   # ordering: ?
rg -n "\b$F\s*[<>]=?\s*\w|\w\s*[<>]=?\s*\w*$F\b" Source/ Plugins/ \
  | rg -v -- "->"                                          # comparisons: ?
```

The `-v -- "->"` matters. Without it, every `Entry->Priority = X` is counted as a
comparison because the arrow contains `>`, and a field that is only ever assigned
looks like a field that is ordered. On the measured reference the naive form
reported two "comparisons"; both were assignments.

A large first number with empty second and third lines is an ordering field that
does not order.

**Guardrail.** An ordering field ships with the comparator that consumes it, in the
same change. If ordering is not implemented yet, do not expose the field.

---

### RA-08 - Tag-driven visibility with the check hardcoded off

**Mechanism.** A widget base class exposes an editable tag container for
"hide when these tags are present". Both consumer sites read
`const bool bHasHiddenTags = false;` with the real expression parked in a comment
next to a TODO. The listener registration that would supply the tags is also a
comment.

**Why it is silent.** `false` is a legitimate value: it means "no hiding tags are
active right now". The widget is visible, which is a normal state, so no test and no
reviewer can tell the difference between "correctly not hidden" and "never able to
hide".

**Why the obvious check misses it.** The TODO admits *one* missing piece and thereby
misdirects. The obvious fix — implement `bHasHiddenTags` — does not restore the
intended behaviour, because a nearby visibility setter overwrites the
designer-authored shown and hidden visibility values on its first call, which arrives
during construction. A stub can be deeper than its own TODO says it is, and a reviewer
who trusts the TODO stops one layer too early.

**Symptom.** A designer fills the tag container, observes nothing, and the class is
recorded in team lore as "the tag hiding does not work" without anyone establishing
why.

**Detect.** Find neutral literals feeding decision branches:

```bash
rg -n "const bool b\w+ = (false|true);\s*//" Source/ Plugins/
```

For each hit, check whether the property that should feed it is `EditAnywhere`. Then
check that nothing else overwrites the same state before the branch is reached — the
second step is the one people skip.

**Guardrail.** An editable property whose consumer is a literal constant must not
ship. When you do implement one, re-derive the whole path rather than the single line
the TODO names.

---

### RA-09 - Parameters threaded through for a subsystem that was never built

**Mechanism.** A `bIsSimulated` flag appears in three method signatures and is
passed through six call sites. Its sole caller passes a literal `false`. A companion
"replace this hit" method exists and is never called; the boolean recording its result
is only ever read.

**Why it is silent.** A flag that is always `false` produces one consistent code
path, which is the path everything is tested on. A method with no callers has no
behaviour to be wrong. Both are inert rather than broken.

**Why the obvious check misses it.** The threading through multiple layers is exactly
what a real, wired-up feature looks like — that shape is itself the disguise. Usage
searches return many hits. Only two narrower questions expose it: is the parameter
ever branched on, and does the sole call site pass a variable or a literal?

**Symptom.** An engineer reads the signatures, concludes server-side hit rewind
exists, and budgets zero for it. The gap is discovered when the game meets real
latency, at which point the structure of abilities, tracing and damage is already
committed.

**Detect.** Find parameters that are carried but never branched on:

```bash
rg -n "\bbIsSimulated\b" Source/                 # many hits: plumbed
rg -n "if\s*\(\s*!?bIsSimulated" Source/         # none: never decides anything
rg -n "\w+\(.*\bfalse\b.*\)" Source/ | rg "bIsSimulated|Simulated"
```

Also list public functions with zero callers: `rg -n "FunctionName"` returning only
the declaration and definition.

**Guardrail.** Do not ship attachment points for a subsystem that does not exist.
An unused parameter is a claim about the architecture; if the claim is false, delete
the parameter or write the subsystem.

---

### RA-10 - Field silently dropped in both directions of a conversion

**Mechanism.** Helper functions convert between a gameplay message and cue
parameters. A context tag container present on both sides is not copied in either
direction. Both sites carry a TODO.

**Why it is silent.** The conversion succeeds and produces a fully valid object. The
dropped field simply arrives empty, and empty is the same value a caller who did not
set it would produce. There is no partial-failure signal because nothing failed.

**Why the obvious check misses it.** Round-tripping is the natural test, and a
round trip through both directions loses the same field consistently — so a
comparison of "before" against "after" on the fields anyone thought to compare
passes. Structural equality is the test that would catch it, and structural equality
is what nobody writes for conversion helpers.

**Symptom.** Effects lose their contextual tags when routed through the conversion,
so downstream selection by context silently picks the default variant.

**Detect.** For every conversion helper, compare field counts on both sides:

```bash
rg -n "^\s*(FGameplayTagContainer|F\w+|TArray<\w+>)\s+\w+;" Source/**/Struct.h
rg -n -A30 "ToOtherForm|FromOtherForm|Convert\w+" Source/ | rg "\bField\b"
```

Any field declared on both types and mentioned in neither direction is dropped.

**Guardrail.** Conversion helpers get a structural round-trip test that enumerates
fields by reflection rather than by hand. A hand-written comparison tests the fields
the author remembered, which is the same set they remembered to copy.

---

### RA-11 - Replicated structure with no callers and an empty removal hook

**Mechanism.** A replicated fast-array serializer type is fully declared, with the
removal callback implemented as an empty body. Nothing in the codebase constructs or
uses it.

**Why it is silent.** Unused replicated types cost nothing at runtime and generate no
warning. The empty callback is a valid override — many are legitimately empty.

**Why the obvious check misses it.** The type is complete and idiomatic, so it reads
as infrastructure that some subsystem depends on. Deleting it feels risky, so it
survives every cleanup. Meanwhile a reader treats its existence as evidence that
replicated messaging is solved.

**Symptom.** A team builds on top of it, assuming it works, and discovers on the
first multi-client test that no path ever populated it.

**Detect.** Find declared-but-unconstructed types:

```bash
rg -ln "struct F\w+ : public FFastArraySerializer" Source/ Plugins/
# per type T:
rg -n "\bT\b" Source/ Plugins/ | rg -v "\.h:|struct|USTRUCT|template"
```

Hits only in the header mean the type has no user.

**Guardrail.** Replication infrastructure ships with at least one caller and one
test that observes a replicated change. Untested replication is not infrastructure,
it is a plan.

---

## C3 — Deliberate sample-scope narrowings

Nothing here is broken. The reference is internally consistent with every one of
these. They become expensive only when the sample becomes the base of a product.

### RA-12 - No lag compensation, and the whole hit chain follows from it

**Mechanism.** The project contains no custom saved-move, server-move or compressed
flags implementation, and therefore no historical positions on the server. Local
targeting early-returns when the pawn is not locally controlled, so the server never
traces. A `bIsTargetDataValid` local is initialised to `true` and consumed as if it
were a validation result. Damage falloff is computed from the client's supplied trace
start, and the material multiplier from the client's supplied physical material.

**Why it is silent.** Every step is the only available behaviour given the missing
subsystem. The server cannot validate positions it never recorded, so trusting the
client is not a slip — it is the sole option. Correct-looking code all the way down,
with the gap one level below the code.

**Why the obvious check misses it.** Reviewing the damage path finds an authority
check and a validity boolean, which together look like a validation layer. The
boolean is a literal and the authority check answers a different question ("may this
instigator damage this target?") than the one that matters ("did this shot happen?").
Reading for the presence of checks finds checks; reading for what the adversary can
assert finds nothing stopping them.

**Symptom.** In production, clients report impossible hits and the diagnosis becomes
"someone forgot a validation call" — which sends engineers to patch individual sites
instead of pricing the missing subsystem.

**Detect.** Ask what the adversary supplies, then trace each such value:

```bash
rg -n "class \w+ : public FSavedMove_Character|ServerMove|CompressedFlags" Source/
rg -n "const bool b\w*Valid\w* = true" Source/
rg -n "TargetData|HitResult" Source/ | rg -i "damage|falloff|physmat"
```

No saved-move type plus client-supplied geometry in the damage math means full
client trust.

**Guardrail.** Choose a hit-registration model *before* borrowing a weapon stack:
server-authoritative with rewind, client-claim with plausibility bounds, or explicit
full trust. Write the choice down. Each has a different cost and a different cheat
surface, and the choice dictates structure you cannot cheaply change later.

---

### RA-13 - Replication graph implemented, configured, and shipped disabled

**Mechanism.** A replication graph implementation and around a dozen tuning cvars
exist. Project config disables it and the class routing table is essentially empty,
with the few entries present marked not-routed.

**Why it is silent.** The default replication path works fine at sample scale.
Disabled infrastructure produces no error and no measurable difference until player
counts and actor counts grow.

**Why the obvious check misses it.** The presence of the implementation, the cvars
and the config section reads as "this is configured". Nobody diffs the routing table
against the actor classes that actually exist, because a populated-looking config
section satisfies the eye.

**Symptom.** Bandwidth and server CPU limits are discovered in beta, at the point
where the actor class layout is fixed and re-routing is a large change.

**Detect.** Compare routing entries against replicated classes:

```bash
rg -n "bDisableReplicationGraph|ClassNodeMapping" Config/
rg -c "GetLifetimeReplicatedProps" Source/ Plugins/
```

A handful of routing entries against dozens of replicated classes means the graph
has never carried traffic.

**Guardrail.** Copying a disabled subsystem's configuration copies untested
configuration. Either enable it and measure under load, or delete the config and
record that you owe the work.

---

### RA-14 - Preload machinery made unreachable by a load-mode constant

**Mechanism.** A cue manager supports delayed loading with garbage-collect and
map-load hooks. A load-mode constant is set to "load upfront", which short-circuits
every switch site — including the one that installs the three delegates.

**Why it is silent.** Loading everything upfront is correct behaviour. The
machinery is not broken; it is bypassed. Memory is higher and nothing reports it,
because nothing is measuring against a budget.

**Why the obvious check misses it.** Searching for the delegates finds them bound in
source, so the wiring appears present. The early return that makes the binding
unreachable is in a different function, guarded by a constant that reads like a
development convenience. The project's own diagnostic command reports zeros, which is
then read as "no cues are preloaded yet" rather than "this counter is dead".

**Symptom.** A team diagnosing memory or hitching concludes the engine's preload
system is broken and descends into engine code, when the sample simply opted out.

**Detect.** Find switch sites gated by a constant, and confirm delegate binding is
reachable:

```bash
rg -n "LoadMode|ELoadMode|EEditorLoadMode" Source/ Plugins/
rg -n -B6 "AddUObject|AddRaw|BindUObject" Source/ | rg "return;|LoadUpfront"
```

**Guardrail.** Distinguish "the mechanism is broken" from "the sample configured it
off" before you spend a day in engine code. Record which subsystems the reference
bypasses; that list is part of what you are adopting.

---

### RA-15 - Public virtual state writers with no authority check

**Mechanism.** Death-state transitions are written by two public virtual methods on
a health component, neither of which checks for network authority.

**Why it is silent.** Single-process play-in-editor never separates authority from
simulation, so the code path is exercised constantly and always on the authority. The
missing check has no observable consequence in the environment where the sample runs.

**Why the obvious check misses it.** Authority checks are usually reviewed at the
RPC boundary, and these methods are not RPCs — they are ordinary virtual functions
that a caller in the right context invokes correctly. Being public and virtual is
what makes it dangerous: the class invites overriding and calling from anywhere, and
the invitation carries no precondition.

**Symptom.** A client-side subclass or a Blueprint calls the method during
prediction, the client's death state diverges from the server's, and the resulting
desync is chased as a replication bug.

**Detect.** List state writers and check each for an authority guard:

```bash
rg -n "void (Start|Finish|Set)\w*(Death|State|Team)\w*\(" Source/
rg -n -A6 "void (Start|Finish|Set)\w*(Death|State|Team)\w*\(" Source/ | rg -c "HasAuthority"
```

A count below the number of writers names the unguarded ones.

**Guardrail.** Every writer of replicated state either checks authority or is
private with a single guarded caller. Public plus virtual plus unguarded is an
invitation.

---

### RA-16 - Faction query fails open on invalid input

**Mechanism.** A team comparison returns an "invalid argument" result for unknown
membership, and the damage path treats anything that is not an explicit "same team"
as damageable. The site carries a TODO calling itself temporary.

**Why it is silent.** Unknown membership does not occur in a sample where every pawn
is assigned a team at spawn. The fail-open branch is never taken, so it is never
observed to be wrong.

**Why the obvious check misses it.** The function returns a three-valued result,
which reads as careful design. The defect is in the *consumer's* collapse of three
values into two, in a different file. Reviewing the query finds correct code;
reviewing the damage path finds a plausible boolean.

**Symptom.** Neutral, spectating or mid-transition actors take or deal damage. The
bug appears only in modes the sample does not have, which is to say, in yours.

**Detect.** Find three-valued results collapsed to booleans:

```bash
rg -n "Invalid|Unknown|Indeterminate" Source/ | rg -i "team|faction|relation"
rg -n -B4 -A4 "CanCauseDamage|CanDamage|IsHostile" Source/
```

Read the branch: does the invalid case land with "allowed" or "denied"?

**Guardrail.** Unknown must be denied, never allowed, on any decision that costs
something. If denial is not acceptable, the unknown state itself is the bug.

---

### RA-17 - No tag or asset redirects declared at all

**Mechanism.** Config declares zero gameplay tag redirects. Every tag name is a hard
string with no migration path.

**Why it is silent.** A project that has never renamed a tag needs no redirects. The
absence is invisible right up to the first rename, and samples do not rename after
release.

**Why the obvious check misses it.** This is an absence with no consumer to inspect
— there is no line of code to review. It is only visible if you go looking for a
capability you have not needed yet, which is exactly the thing nobody does during
adoption.

**Symptom.** The first tag rename after content exists breaks every asset that
referenced it. Since references live in binary assets, the breakage is silent data
loss rather than a compile error, discovered per-asset over weeks.

**Detect.**

```bash
rg -c "GameplayTagRedirects|\+ActiveGameRedirects|ClassRedirects" Config/
```

Zero, in a project that has shipped content, means renames have not yet happened —
not that they are safe.

**Guardrail.** Establish redirect discipline before the first rename, not after.
Add a CI check that a removed tag name has a corresponding redirect entry.

---

### RA-18 - Server RPC declared without validation

**Mechanism.** A quick-bar style component exposes a `Server, Reliable,
BlueprintCallable` function with no `WithValidation`, accepting an index from the
client.

**Why it is silent.** Well-behaved clients send valid indices, and the sample only
ever has well-behaved clients. Out-of-range access either clamps harmlessly or hits a
path no test covers.

**Why the obvious check misses it.** Nearby functions are marked
`BlueprintAuthorityOnly`, which reads as an access restriction and satisfies a
reviewer scanning for guards. That specifier constrains Blueprint execution context
only — it does not validate parameters, and it does not constrain C++ callers at all.
A guard that answers a different question is worse than no guard, because it stops
the search.

**Symptom.** A modified client sends an arbitrary index. Depending on the container,
this is a crash, a read of unrelated memory, or equipping something the player never
earned.

**Detect.**

```bash
rg -n "UFUNCTION\([^)]*\bServer\b[^)]*\)" Source/ Plugins/ | rg -v "WithValidation"
```

Every hit takes client-controlled input on trust.

**Guardrail.** Every server RPC validates its parameters, including range and
ownership, and `BlueprintAuthorityOnly` is never counted as validation.

---

### RA-19 - Readiness gate admits simulated proxies with no controller

**Mechanism.** An initialisation-state transition treats "has a controller" as a
precondition, but admits simulated proxies that have none, so readiness is reached
on different grounds depending on net role.

**Why it is silent.** Both branches produce "ready", and ready is the state everything
downstream waits for. No consumer asks *why* readiness was granted.

**Why the obvious check misses it.** The gate is short and reads as a careful
role-aware special case — which is what it is. The problem is that "ready" then means
two different things, and the divergence lives in every consumer rather than in the
gate. Reviewing the gate finds nothing wrong.

**Symptom.** Systems that assume a controller exists after readiness crash or
no-op on simulated proxies. The failure appears only with a remote client, so it
survives all local testing.

**Detect.** Find role-dependent readiness and enumerate its consumers:

```bash
rg -n -B4 -A10 "CanChangeInitState|HasReachedInitState" Source/ | rg "IsLocallyControlled|GetController|ROLE_SimulatedProxy"
rg -n "HasReachedInitState|GameplayReady" Source/ | wc -l
```

**Guardrail.** One readiness state means one set of guarantees. If proxies reach it
by a different route, they need a different state name, so consumers must choose.

---

## How to use this list

Do not read it as a defect report about someone else's project. Read it as a list of
**question shapes**:

1. Which of my editable properties has no writer?
2. Which of my ordering fields never reaches a comparison?
3. Which of my decision branches reads a literal?
4. Which of my parameters is threaded but never branched on?
5. Which of my unknown-input paths fails open?
6. Which of my public state writers has no authority check?
7. Which of my capabilities exists only as configuration that is switched off?

Each has a one-line `Detect` above. Run all seven against your own tree before you
run any of them against the reference.

## Evidence boundary

Every entry was read in source in one reference project on one engine version. They
are worked examples of the classification, not a defect list to carry into other
engine versions or other samples. An entry that does not reproduce under its own
`Detect` in your tree does not apply to you.
