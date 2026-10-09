# Failure modes: input architecture

Eleven ways a tag-addressed input layer binds correctly and never fires.

The shared property is unusually literal here: **the ability input path has no
error case.** A press resolves to a tag, the tag is compared against granted
ability specs, and no match means no activation. That is the same code path as
"you do not currently have this ability", which is a normal state. Nothing logs,
because from the framework's view nothing went wrong.

The native path is louder — an unresolved tag produces an error at bind time —
which is worth knowing when triaging: **if the button is native and silent, the
problem is upstream of the config; if it is an ability and silent, the problem
could be anywhere along seven assets.**

Recipes use `rg` from a project's source root, and were executed against the
audited project while this file was written.

---

## The join

### IN-01 - Tag lookup is exact, and the hierarchy suggests otherwise

**Mechanism.** The ability spec lookup compares the pressed tag against the
spec's dynamic source tags with an exact match. A spec tagged with a parent is
not found by a press of its child.

**Why it is silent.** No match means no activation, which is indistinguishable
from not having been granted the ability. There is no "close match" concept to
warn about.

**Why the obvious check misses it.** Everything else about the tag layer is
hierarchical — the editor picker filters by category, the vocabulary is a tree,
and neighbouring systems in the same codebase do use hierarchical matching. The
reasonable assumption is wrong here, and nothing at either the config or the
ability-set end states the matching semantics.

**Symptom.** An ability that is granted, bound, and correct in every inspectable
respect simply does not activate. Designers re-author the tag, re-save the
assets, and eventually route around it by duplicating the leaf.

**Detect.** Read the comparison and confirm the semantics, then check whether any
authored tag relies on the other one:

```bash
rg -n "HasTagExact|MatchesTag" --glob "*.cpp" . | rg -i "input|spec"
```

Then list every input tag used on an ability spec and every tag used in a config,
and confirm the sets are equal rather than merely overlapping. In the audited
project both lookup sites use exact matching, on adjacent lines.

**Guardrail.** State the matching semantics in a comment at the lookup and in the
tag namespace's own documentation. If hierarchical matching is wanted, implement
it deliberately — do not let readers infer it from the tag shape.

---

### IN-02 - Two tag sources for one namespace

**Mechanism.** Native input tags are declared in C++ as compile-time symbols;
ability input tags are declared in a config file as strings. Both live under the
same namespace root.

**Why it is silent.** Both work. The engine resolves both to the same registry,
and a tag from either source behaves identically at runtime.

**Why the obvious check misses it.** Looking at either source shows a complete,
well-organised list. There is no artefact anywhere that shows both, so the
vocabulary appears smaller than it is and its split appears not to exist.

**Symptom.** An audit of the input vocabulary misses half of it. A rename sweep
covers one source. A developer looking for a tag symbol in C++ concludes a tag
does not exist when it is declared in config.

**Detect.** Count both sources and compare against the namespace:

```bash
rg -n 'UE_DEFINE_GAMEPLAY_TAG\w*\([^,]+,\s*"InputTag\.' --glob "*.cpp" .
rg -n 'GameplayTagList=\(Tag="InputTag\.' Config/ Plugins/*/Config/
```

Both non-empty is the finding. In the audited project the native movement tags
come from C++ and the ability tags from config, and the two sets do not overlap
at all — which is a defensible split, undocumented.

**Guardrail.** One namespace, one declaration source, documented. If a split is
deliberate, draw the line at a sub-namespace boundary and write it down where
both halves are visible.

---

## Ownership and teardown

### IN-03 - Bind handles discarded, making removal impossible

**Mechanism.** The binding helper returns handles through an out-parameter. Both
callers declare that array as a local and let it fall out of scope.

**Why it is silent.** The bindings work perfectly. Handles are needed only to
undo, and nothing undoes during a normal session — pawns are recreated between
matches, which disposes of the input component and hides the leak.

**Why the obvious check misses it.** The out-parameter is passed correctly, the
call is idiomatic, and a removal function exists elsewhere in the class. The
defect is the *storage duration* of a local variable, which no review of API
usage examines.

**Symptom.** Deactivating a feature leaves its ability bindings on a live pawn.
Harmless while the ability is also revoked — the tag reaches the component and
finds no spec — but a re-grant resurrects phantom input.

**Detect.** Find handle arrays declared at the call site rather than as members:

```bash
rg -n -B3 "BindAbilityActions|BindAction\(" --glob "*.cpp" . \
  | rg "TArray<uint32>\s+\w+;|TArray<\w*Handle>\s+\w+;"
```

In the audited project this appears at two sites in one component: the initial
binding and the feature-driven addition.

**Guardrail.** Handles live on the object whose lifetime governs the binding,
stored in the same change that creates them. If there is nowhere to store them,
the input is not removable and that must be stated before it ships.

---

### IN-04 - Removal API that exists and does nothing

**Mechanism.** The class exposes a removal function whose body is a comment. A
feature action calls it during teardown.

**Why it is silent.** The call compiles and returns. Nothing distinguishes
"removed the bindings" from "did nothing", because neither returns a result.

**Why the obvious check misses it.** The teardown path *is* implemented in the
feature action — it iterates its tracked pawns and calls removal on each — so a
review of the action finds a complete, symmetric implementation. The empty body
is one call away in a different subsystem.

**Symptom.** As IN-03, from the other end. A team scopes "implement the missing
removal" from the empty function, and finds the estimate was an order of
magnitude low because the handles no longer exist to remove.

**Detect.** Find removal functions with no statements, and dead removal helpers:

```bash
rg -n -A4 "void \w+::Remove\w+\(" --glob "*.cpp" . | rg -B2 "@?TODO"
rg -c "RemoveBinds|RemoveBindingByHandle" --glob "*.cpp" --glob "*.h" .
```

The second command matters: in the audited project a working removal helper
exists on the input component and has **zero callers** — the mechanism is
present, and the data it needs was thrown away by IN-03.

**Guardrail.** A removal function with no body must not compile quietly: make it
pure virtual, assert, or delete the caller. Then check that its helper has at
least one caller — a correct utility nobody can call is the same as no utility.

---

### IN-05 - Tracking container that is never written

**Mechanism.** The context-adding action keeps a list of the controllers it
touched, removes from it, and iterates it during reset — but the add path takes
the per-context data as a parameter and never writes to it.

**Why it is silent.** The reset loop finds the list empty and completes. Contexts
still come off, but only reactively — when the receiver is reported as going
away — so behaviour depends on teardown order.

**Why the obvious check misses it.** Four of five operations on the container
exist, including an assertion at activation that it starts empty. Any check of
"is this container used?" answers yes emphatically. Only the producer is missing.

**Symptom.** Mapping contexts survive feature deactivation when the receiving
controller outlives the feature. Intermittent, ordering-dependent.

**Detect.** Compare reads against writes per container:

```bash
C='ControllersAddedTo'
rg -n "\b$C\b" --glob "*.cpp" --glob "*.h" .
rg -n "\b$C\b\s*\.\s*(Add|AddUnique|Emplace|Push)" --glob "*.cpp" .
```

In the audited project the second search is empty, the authors left a comment on
the reset path noting exactly that, and a sibling action in the same directory
does the equivalent correctly — so the two files diff against each other.

**Guardrail.** A container whose only mutations are removals has no producer.
Assert non-empty after the add path runs.

---

## Configuration traps

### IN-06 - One flag secretly gating two operations

**Mechanism.** Registering a context for rebinding and activating it are separate
operations. In one code path the activation call is nested **inside** the
`if` that tests the register-with-settings flag.

**Why it is silent.** Both operations are legitimate and both are performed when
the flag is set — which it is by default. Nothing about the default case is
wrong, so the coupling never manifests during development.

**Why the obvious check misses it.** The flag's name describes exactly one of the
two things it controls. A designer reading the property, and a reviewer reading
the property, both understand it correctly and neither is looking at the brace
structure twenty lines away. Worse: the *same* project has a second
implementation of the same feature where the flag correctly controls only
registration, so a reader who checks one path and generalises is wrong.

**Symptom.** Unchecking "expose this for rebinding" makes the character stop
responding entirely, with nothing in the log. Diagnosed as an asset problem.

**Detect.** Find activation calls nested inside a settings-registration branch:

```bash
rg -n -B8 "AddMappingContext\(" --glob "*.cpp" . | rg "bRegisterWithSettings|RegisterInputMappingContext"
```

Any hit is the finding. Then check every other implementation of the same
operation in the project and compare — the discrepancy between two paths is
stronger evidence than either path alone.

**Guardrail.** Registration and activation are separate statements at the same
brace level, each guarded by its own condition. Test all four combinations of the
two flags, because all four are meaningful.

---

### IN-07 - Nested condition that disables an unrelated feature

**Mechanism.** The loop that applies default mapping contexts sits inside an
`if` that tests for a semantic config. A pawn with no config therefore gets no
contexts either.

**Why it is silent.** Every shipped pawn has a config, so the guard is always
true and the nesting is never exercised. The two things are unrelated in concept
and adjacent in code.

**Why the obvious check misses it.** The guard is correct for the block it was
written for. The extra scope it captures is a brace position, not a statement,
and nothing names the coupling.

**Symptom.** A new pawn archetype authored without a config is completely
unresponsive — not "no abilities", but no movement, no look, nothing. Read as a
much deeper problem than a missing asset reference.

**Detect.** Read the initialization function's brace structure:

```bash
rg -n -A25 "::InitializePlayerInput" --glob "*.cpp" . | rg -n "if \(|for \(|AddMappingContext"
```

A mapping-context loop indented inside a config guard is the finding.

**Guardrail.** Contexts and configs are independent inputs to initialization and
belong in sibling blocks. Validate that a pawn without a config is a deliberate
configuration rather than a broken one.

---

### IN-08 - Clearing all mappings, then relying on a broadcast to restore them

**Mechanism.** Pawn input initialization clears every mapping on the subsystem
before adding its own — removing contexts that active features added earlier. A
readiness broadcast afterwards prompts those features to re-add theirs.

**Why it is silent.** It works, because the broadcast happens and the features
listen. Correctness is real; it is just a property of event ordering rather than
of stored state.

**Why the obvious check misses it.** The clear is a defensible line with an
obvious intent — start from a known state. The features' re-add is in a different
file, reached by an event. Nothing at the clear site says what it is destroying,
and nothing at the re-add site says why it is necessary.

**Symptom.** A feature's input disappears when a pawn re-initializes, in any
ordering where that feature does not receive or does not act on the ready event —
a feature activated during the broadcast, one whose handler early-returns, or one
whose receiver is not yet registered.

**Detect.** Find the clear and confirm the recovery path:

```bash
rg -n -A3 "ClearAllMappings" --glob "*.cpp" .
rg -n "SendGameFrameworkComponentExtensionEvent" --glob "*.cpp" . -B4
```

A clear with no explicit re-application, relying on an event broadcast elsewhere,
is the finding. In the audited project the flag that gates readiness is set
*before* the broadcast — the correct order, and worth verifying rather than
assuming.

**Guardrail.** Either do not clear what you do not own, or re-apply from a stored
list rather than from a broadcast. If the broadcast is the mechanism, comment it
at the clear site so the dependency is visible from both ends.

---

## Cost and misleading surfaces

### IN-09 - Legacy axis configuration beside Enhanced Input

**Mechanism.** The project input config retains legacy axis entries — dead zones,
sensitivities — while actual sensitivity and dead zone are applied by input
modifiers.

**Why it is silent.** The legacy values are read by the legacy path, which is not
in use. Changing them does nothing, and doing nothing produces no error.

**Why the obvious check misses it.** They are exactly where a developer would
look for sensitivity, with exactly the names they would search for. The file
answers the question asked; the answer is stale.

**Symptom.** Time lost tuning values that have no effect, and a plausible but
wrong belief about where input tuning lives — which then propagates into
documentation.

**Detect.** Compare the legacy entries against the modifiers that really apply:

```bash
rg -n "AxisConfig|Sensitivity=|DeadZone" Config/*.ini
rg -n "class \w*InputModifier" --glob "*.h" .
```

Both non-empty is the finding. In the audited project eleven legacy axis entries
coexist with four modifiers that read player settings, and the modifiers win.

**Guardrail.** Delete legacy entries the engine does not require, or annotate them
in place as inert with a pointer to the modifiers. A misleading config is more
expensive than a missing one.

---

### IN-10 - Setting resolved by property name through reflection

**Mechanism.** An input modifier scales a value by looking up a settings property
**by name** through reflection, with a cache.

**Why it is silent.** A rename produces no compile error, because the name is a
string in data. The lookup fails at runtime and the modifier returns unscaled
input — a plausible value.

**Why the obvious check misses it.** Renaming a property is exactly the operation
IDEs make safe. The developer performs a rename refactor, everything compiles,
every reference updates, and this one does not because it is not a reference.

**Symptom.** Sensitivity, inversion or dead zone silently stops respecting the
player's setting after an unrelated refactor. Reported as "the setting does
nothing" long after the rename.

**Detect.** Find name-based property resolution:

```bash
rg -n "FindPropertyByName|FindFProperty|GetPropertyByName" --glob "*.cpp" .
```

Each hit is a link the compiler does not check. Add a startup assertion for each.

**Guardrail.** Resolve settings through typed accessors. Where reflection is
unavoidable, assert at startup that every name resolves, so a rename fails loudly
at launch rather than quietly in gameplay.

---

## Loading

### IN-11 - Blocking load on the pawn initialization path

**Mechanism.** A mapping context soft reference is resolved with a synchronous
load during pawn input initialization.

**Why it is silent.** It succeeds. The asset arrives, input works, and the cost is
a stall measured in milliseconds on a warm cache.

**Why the obvious check misses it.** A synchronous load is the simplest correct
code, and correctness is what review checks. The cost appears only on a cold
cache, on slower storage, or at a moment — player spawn — that nobody profiles
because it happens before the part they were measuring.

**Symptom.** A hitch at spawn that is attributed to the level, the character mesh
or the ability system, because the input layer is not where anyone looks for a
frame spike.

**Detect.** Find synchronous loads on initialization paths, and contrast them with
the bare accessors elsewhere:

```bash
rg -n "LoadSynchronous\(\)" --glob "*.cpp" . -B6 | rg "Init|BeginPlay|Setup"
rg -n "\.Get\(\)" --glob "*.cpp" . -A2 | rg -v "ensure|check|if\s*\(|UE_LOG"
```

The pairing is the interesting part: the audited project loads synchronously on
the base path and uses bare, unguarded accessors on the feature paths — so one
route hitches and the other silently skips when a bundle did not load.

**Guardrail.** Preload input assets with the bundle that owns them and resolve
with a guarded accessor that logs on failure. Neither blocking nor silently
skipping is acceptable on a path this visible.
