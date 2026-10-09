# Failure modes: modular gameplay

Nineteen ways a feature attaches correctly and detaches incompletely.

The shared property is stated once, because it explains the whole list:
**activation is what gets demonstrated.** A feature is switched on, someone
checks the ability appeared, the widget rendered, the input worked, and the
review is done. Deactivation is exercised by nobody during development, because
in development you restart the editor instead. So the broken half is
systematically the half nobody looks at, and its symptoms — a duplicate on the
second activation, a bind that survives its feature — appear later and are
attributed elsewhere.

A second property applies to most entries: the reference implementations of these
actions **look symmetric**. There is an `Add` and there is a `Remove`, a reset
loop and a reactive removal path. The defect is almost never a missing function;
it is a function that removes something other than what was added, or that reads
a container nobody fills.

Recipes use `rg` and are written to be run from a project's source root. Most are
a pair: one search finds the addition, the other looks for the matching removal.

---

## Teardown

### MG-01 - Rollback function with an empty body

**Mechanism.** An action's removal path calls a method on a game component, and
that method's body is a comment saying it is not implemented yet.

**Why it is silent.** Every caller succeeds. The call compiles, executes and
returns; nothing distinguishes "removed the bindings" from "did nothing" at the
call site, because neither returns a result.

**Why the obvious check misses it.** The action's teardown *is* implemented and
reads correctly — it iterates its tracked pawns and calls a removal method on
each. Reviewing the action finds a complete, symmetric implementation. The empty
body is one call away, in a different file owned by a different subsystem, and it
is the game component's problem rather than the feature's.

**Symptom.** Ability input bindings survive the deactivation of the feature that
added them. The second activation adds a second set. Nothing errors.

**Detect.** Find removal functions whose body is only a comment:

```bash
rg -n -A4 "void \w+::Remove\w+\(" --glob "*.cpp" . \
  | rg -B2 "^\s*//\s*@?TODO|^\s*\}"
```

Read each hit: a `Remove` whose body contains no statements is the finding. In
the measured reference the removal of an additional input config was exactly this
— a three-line function containing one TODO comment.

**Guardrail.** A removal function with no body must not compile silently. Make it
pure virtual, assert inside it, or delete the caller. An unimplemented rollback
that is *called* is worse than one that does not exist, because the call site
proves the intent was there.

---

### MG-02 - Bind handles discarded at the moment they are created

**Mechanism.** A binding call takes an out-parameter array of handles. The caller
declares that array as a local variable and lets it go out of scope.

**Why it is silent.** The bindings work. Handles are only needed to undo, and
nothing undoes during a normal session.

**Why the obvious check misses it.** The out-parameter is passed correctly and
the call is idiomatic — some codebases even name the argument in a comment at the
call site, which makes it look deliberate. The defect is the *storage duration*
of a local variable, which no search for "is the API used correctly?" examines.
This is also the root cause of MG-01: the removal function cannot be implemented,
because the information it would need was thrown away one function earlier.

**Symptom.** Rollback is not merely unimplemented but *impossible* without
changing the component that binds. An estimate of "implement the missing removal"
comes out an order of magnitude low.

**Detect.** Find handle arrays declared as locals at a binding call:

```bash
rg -n -B2 "BindAbilityActions|BindAction\(" --glob "*.cpp" . \
  | rg "TArray<uint32>\s+\w+;|TArray<FInputBindingHandle>\s+\w+;"
```

Any handle container declared in the same scope as the call, rather than as a
member, is discarded. In the measured reference this appeared at two separate
call sites in one component.

**Guardrail.** Handles returned by a binding API are stored by the object whose
lifetime governs the binding, in the same change that creates the binding. If
there is nowhere to store them, the feature is not removable and that must be
stated before it ships.

---

### MG-03 - Tracking container that is read but never written

**Mechanism.** An action declares a container of the actors it has affected,
removes from it in the reactive path, iterates it during reset — and never adds
to it. The function that would add takes the per-context data as a parameter and
ignores it.

**Why it is silent.** The reset loop runs, finds the container empty, and
completes successfully. An empty loop is a legal outcome; it looks exactly like a
feature that affected nothing because no receivers existed.

**Why the obvious check misses it.** Every symptom of correctness is present: the
container is declared, an `ensure` at activation asserts it starts empty, the
reset loop pops from it correctly, and the reactive path removes from it. Four of
the five operations exist. Only the write is missing, and "is this container
used?" answers yes at four sites.

**Symptom.** Input mapping contexts are never removed at deactivation. They come
off only if the receiving actor happens to die first and the reactive path fires.
The result depends on teardown order, which makes it intermittent.

**Detect.** For every tracking container, compare reads against writes:

```bash
C='ControllersAddedTo'
rg -n "\b$C\b" --glob "*.cpp" --glob "*.h" .                    # all uses
rg -n "\b$C\b\s*\.\s*(Add|AddUnique|Emplace|Push)" --glob "*.cpp" .   # writes only
```

Uses without writes is the finding. The measured reference is unusually clear
here: a sibling action in the same directory tracks its pawns with
`AddUnique` in exactly the place the broken one omits it, so the two files can be
diffed against each other. The original authors had also left a comment on the
broken line noting that the container is never modified — a known defect that
shipped.

**Guardrail.** A container whose only writes are removals is a container with no
producer. Assert non-empty after the add path runs, or derive the collection from
the resource itself rather than maintaining a parallel list.

---

### MG-04 - Reset path narrower than the reactive removal path

**Mechanism.** An action has two removal routes: a reset invoked at deactivation,
and a per-actor removal invoked when the manager reports a receiver going away.
The per-actor route cleans up more than the reset does.

**Why it is silent.** The reset completes and clears its own bookkeeping, so the
action's internal state is consistent afterwards. What is left behind lives in
another subsystem — a pushed layout widget still on its layer — and that
subsystem was never told.

**Why the obvious check misses it.** Both functions exist and both are correct
for what they enumerate. Comparing them requires reading two loops in different
parts of a file and noticing that one iterates two collections and the other
iterates one. Nothing names the missing collection.

**Symptom.** A layout widget pushed by a feature stays on screen after the
feature is deactivated. On reactivation there are two.

**Detect.** Enumerate what each removal path touches and diff the sets:

```bash
rg -n -A20 "::Reset\(" --glob "*.cpp" . | rg "Empty\(|Unregister|Deactivate|Remove"
rg -n -A20 "::Remove\w+\(" --glob "*.cpp" . | rg "Empty\(|Unregister|Deactivate|Remove"
```

A collection handled in the second output and absent from the first is the
finding.

**Guardrail.** One removal implementation, called by both routes. If they must
differ, the reset calls the per-actor removal in a loop rather than reimplementing
a subset of it.

---

### MG-05 - Two removal semantics for one logical resource

**Mechanism.** The same kind of resource is revoked differently depending on which
field granted it: one path clears immediately, the other defers removal until the
resource finishes naturally.

**Why it is silent.** Both are legitimate APIs with legitimate uses. Deferred
removal is correct when an ability is mid-activation; immediate removal is
correct when tearing down. Neither errors.

**Why the obvious check misses it.** Each call site is individually defensible,
and they are in different functions. The inconsistency is only visible if you ask
"what happens to a granted ability at deactivation?" and discover the answer is
"it depends which field you used", which is not a question the code invites.

**Symptom.** Deactivation behaviour differs between two configurations that a
designer considers equivalent. Timing-dependent, so it reproduces inconsistently.

**Detect.** List every revocation call for one resource kind and compare:

```bash
rg -n "ClearAbility|SetRemoveAbilityOnEnd|RemoveActiveGameplayEffect|RemoveSpawnedAttribute" \
  --glob "*.cpp" .
```

Two different revocation calls for the same resource kind in one teardown path is
the finding.

**Guardrail.** Pick one semantic per resource kind and document it at the grant
site. If both are genuinely needed, the choice belongs in the data, named, not in
which code path happened to grant it.

---

### MG-06 - Removal that is not idempotent

**Mechanism.** Resources come off by two independent routes — explicit reset at
deactivation, and reactive removal when the actor dies first. If removal assumes a
record exists, running it twice or in the wrong order misbehaves.

**Why it is silent.** In the common ordering — feature deactivates while actors
are alive — only one route runs. The double-run needs an actor destroyed during
teardown, which is a shutdown-order accident.

**Why the obvious check misses it.** Each route is correct in isolation. Nothing
in either function says "this may also be reached from the other path"; the
coupling is a property of the manager's event dispatch, which is engine code.

**Symptom.** An assert or a stale entry during shutdown, in an ordering nobody can
reproduce on demand.

**Detect.** Check that removal is guarded by record existence, and that reset
loops tolerate mutation:

```bash
rg -n -A8 "::Remove\w+\(" --glob "*.cpp" . | rg "Find\(|Contains\(|if\s*\("
rg -n -A6 "while\s*\(!\w+\.IsEmpty\(\)\)" --glob "*.cpp" .
```

The second pattern is the correct shape: a reset written as "while not empty,
take the top and remove it" survives a removal that mutates the same collection.
A plain range-for over a collection that removal mutates does not.

**Guardrail.** Removal operates on the presence of a record, never on the
assumption of one. Write reset loops as drain loops.

---

## Correctness of what gets attached

### MG-07 - Index incremented inside the guard it is guarding

**Mechanism.** A loop builds one deferred callback per configuration entry,
passing the entry's index as payload. The increment sits inside the branch that
skips invalid entries, so after any skip the payload index no longer matches the
list.

**Why it is silent.** Every index remains in range and resolves to a real entry.
The callback applies a valid, well-formed configuration — just the wrong one.
There is no out-of-bounds access and nothing to assert on.

**Why the obvious check misses it.** Reading the loop shows an increment that
appears to advance per iteration; it takes reading the brace structure to see it
is inside the guard. Editor-time validation flags the invalid entry that triggers
it, so the condition is believed impossible — but that validation is an editor
check, not a runtime guarantee, and it does not run on cooked data.

**Symptom.** Actors receive another entry's abilities. Because both sets are
valid, this presents as a design or data error and gets investigated in the
content.

**Detect.** Find counters incremented inside a conditional within a loop:

```bash
rg -n -B8 "\b\w*Index\+\+|\+\+\w*Index" --glob "*.cpp" . | rg "if\s*\(|continue"
```

Read each hit's brace structure. In the measured reference the increment sat
inside a null-class guard, six lines below the `if` that opened it.

**Guardrail.** Derive the index from the loop itself rather than maintaining a
parallel counter. If a counter is needed, increment it in the loop header where
its relationship to the iteration is structural.

---

### MG-08 - Soft reference resolved with a bare accessor and no fallback

**Mechanism.** An action resolves a soft class or asset pointer with a
non-loading accessor. If the bundle did not load it, the accessor returns null
and the entry is skipped.

**Why it is silent.** The skip is unconditional and unlogged. A feature that
grants nothing looks identical to a feature whose grant list is empty, and both
are legal.

**Why the obvious check misses it.** Every call site is correct given the
precondition "bundles are loaded", which is true in the editor, where everything
is loaded. The precondition is established in a completely different subsystem —
asset bundle configuration — and the code that depends on it does not state that
it does.

**Symptom.** A packaged build silently omits abilities, widgets or mappings that
work in the editor. Bisecting finds nothing, because no code changed.

**Detect.** Compare loading resolutions against non-loading ones, and check for a
fallback:

```bash
rg -c "LoadSynchronous" --glob "*.cpp" .
rg -n "\.Get\(\)" --glob "*.cpp" . -A2 | rg -v "ensure|check|if\s*\(|UE_LOG"
```

In the measured reference the feature-action directory used three synchronous
loads against ten bare accessors, none of the latter guarded or logged. Both
numbers matter: the loads are a runtime hitch, the bare accessors are a silent
omission, and they appear in the same files.

**Guardrail.** Either load, or assert, or log — never skip silently. A soft
reference that is expected to be bundle-loaded should assert that it was.

---

### MG-09 - Unreachable code after a return

**Mechanism.** A validation function returns its result and is followed by a
second, unreachable return.

**Why it is silent.** It is genuinely harmless. The compiler may not even warn.

**Why the obvious check misses it.** It is invisible to behaviour-driven review
because it has no behaviour. It is included here for one reason: **it is evidence
about the file rather than a defect in it.** Dead code after a return means
someone edited this validation and did not read what followed. Treat it as a
marker for where attention lapsed, and read the surrounding function more
carefully than you otherwise would.

**Symptom.** None. Its value is diagnostic.

**Detect.**

```bash
rg -n -A3 "^\s*return \w+;\s*$" --glob "*.cpp" . | rg -A1 "^\s*$" | rg "return"
```

**Guardrail.** Enable and honour unreachable-code warnings. Where one appears,
re-read the function rather than only deleting the line.

---

## Context and scope

### MG-10 - Action state in plain members rather than per-context

**Mechanism.** One action object can be active in several state-change contexts
simultaneously — client and server in a single process is the ordinary case.
State kept in plain member fields is shared between them.

**Why it is silent.** With one context, which is every standalone run, the
behaviour is correct. The corruption requires two contexts, and the second
context's writes look like legitimate updates.

**Why the obvious check misses it.** Member fields on an action object are the
obvious place to keep state, and nothing in the base class signature suggests
otherwise. The requirement is transmitted only by convention — a context
parameter that every lifecycle method receives and that a single-context
implementation can safely ignore.

**Symptom.** One process's client and server tread on each other's tracking data.
Teardown removes the wrong context's resources, or removes them twice.

**Detect.** Find action state that is not keyed by context:

```bash
rg -n -A12 "class \w*GameFeatureAction\w*" --glob "*.h" . \
  | rg "^\s*(TArray|TMap|TSet|TSharedPtr|bool|int32)\s+\w+" \
  | rg -v "FGameFeatureStateChangeContext"
```

Any mutable member that is not inside a per-context map is a candidate. The
correct shape — a per-context struct in a map keyed by the change context —
appears in four separate actions in the measured reference and is worth copying
verbatim.

**Guardrail.** All action state lives in a per-context map. Assert at activation
that the context's slot is empty, and reset it if not — that assertion is what
turns a silent leak into a visible one.

---

### MG-11 - Activation reference count compiled out of shipping

**Mechanism.** A count that prevents one owner from deactivating a plugin another
still needs is wrapped in an editor-only guard, and additionally checked against
an editor runtime flag inside.

**Why it is silent.** In the editor, where multiple worlds share a process, the
count is present and correct. In a shipping build there is one world per process,
so the case it protects against does not arise — until it does.

**Why the obvious check misses it.** The mechanism exists, is correct, and is
tested every time anyone uses multi-world play-in-editor. Discovering that it does
not ship means reading the preprocessor guard around it, which is at the top of a
file nobody opens while reasoning about deactivation.

**Symptom.** No symptom in a single-world build. A latent hazard the moment any
build hosts two experiences, which is exactly when a project starts caring about
modularity.

**Detect.**

```bash
rg -n -B4 -A10 "RequestToDeactivate|NotifyOfPluginActivation|ActivationCount" \
  --glob "*.cpp" . | rg "#if|GIsEditor|WITH_EDITOR"
```

A reference count inside an editor guard, in code that ships, is the finding.

**Guardrail.** Reference counting is a correctness mechanism, not a development
convenience. If it only exists in the editor, say so where it is declared and
state what protects shipping instead.

---

### MG-12 - Plugins leak enabled between experiences

**Mechanism.** Experience teardown deactivates the plugins it listed, but a switch
between experiences is not implemented as a diff — so plugins required by the old
experience and not the new one may stay enabled.

**Why it is silent.** An enabled plugin that nothing uses has no symptom. Its
content stays resident and its actions have already been deactivated, so the
observable state is correct.

**Why the obvious check misses it.** Deactivation exists and works for the case it
was written for: ending play. Experience-to-experience switching is a different
lifecycle that reuses the same teardown, and nothing in that teardown announces
its scope.

**Symptom.** Memory that does not return to baseline across mode changes, and a
second experience that inherits capabilities from the first.

**Detect.** Look for the diff, and for the authors' own admissions:

```bash
rg -n -i "//\s*@?TODO.*(leak|deactivat|unload|experience)" --glob "*.cpp" .
rg -n "GameFeaturePluginURLs" --glob "*.cpp" . -B4 -A8 | rg "Difference|Intersect|Diff"
```

The first search matters more than the second. In the measured reference the
experience manager carries an eight-item block of the authors' own TODOs, one of
which states plainly that plugins are leaked enabled and that diffing requirements
is the intended fix. **A defect the authors documented is the cheapest one you
will ever find** — read those blocks first in any codebase you are adopting.

**Guardrail.** Implement the requirement diff, or define experience changes as
map-travel-only and write that decision down. An undefined middle is what leaks.

---

### MG-13 - Editor loads both role bundles

**Mechanism.** The loading policy loads client data when not a dedicated server
and server data when not a client-only build. In the editor neither condition
excludes, so both load.

**Why it is silent.** It is intentional and it is correct — the editor must be
able to run either role. Nothing is wrong; the number it produces simply describes
no shipping configuration.

**Why the obvious check misses it.** Profiling produces a figure, and figures from
a profiler carry an authority their provenance does not. The condition that
inflates it is two boolean expressions in a policy class, in a different
subsystem from the one being measured.

**Symptom.** Memory and load-time budgets built on editor measurements, wrong in a
direction that feels safe until a platform limit is real.

**Detect.**

```bash
rg -n -A6 "GetGameFeatureLoadingMode|bLoadClientData|bLoadServerData" --glob "*.cpp" .
```

If neither flag excludes in the editor, both bundle sets load. In the measured
reference the authors noted the resulting editor hitching in a comment beside it.

**Guardrail.** Editor asset measurements are directional only. Any absolute budget
requires a packaged build of the target role, and any budget quoted without one
carries that caveat in writing.

---

## Timing and readiness

### MG-14 - A delay with no named dependency

**Mechanism.** Selection or initialisation is deferred by a tick to let something
else finish first.

**Why it is silent.** It works. One frame is enough today, on this machine, for
this content set.

**Why the obvious check misses it.** A next-tick deferral is a common, accepted
idiom, and the code around it is correct. Whether it is legitimate depends
entirely on whether the thing being waited for is *named* — and an unnamed wait
looks identical to a named one.

**Symptom.** Initialisation order breaks on a slower machine, a larger content
set, or after an unrelated subsystem changes its own timing. The failure appears
far from the deferral.

**Detect.** Find deferrals and check for a stated prerequisite:

```bash
rg -n -B6 "SetTimerForNextTick|GetTimerManager\(\)\.SetTimer" --glob "*.cpp" . \
  | rg -i "//|comment|wait|until|so that"
```

A deferral whose surrounding comment names what it waits for is debt with a
receipt. One with no comment is debt with a timer wrapped around it. In the
measured reference the one-frame delay before experience selection *is*
documented — it waits for startup settings — which is the correct form.

**Guardrail.** Every delay names its prerequisite in a comment at the call site,
and is replaced by an explicit readiness signal when one becomes available.

---

### MG-15 - Handler attached to the generic extension event

**Mechanism.** An action registers for "extension added", which fires when the
manager first learns of the actor — before its pawn data, ability system,
controller or input exist.

**Why it is silent.** The handler runs, finds what it needs missing, and returns
without acting. Returning early on a missing prerequisite is defensive
programming, and looks like it.

**Why the obvious check misses it.** The registration is correct, the handler is
correct, and the early return is correct. Nothing is wrong at any single point.
The feature simply never applies, because the one event that would have carried it
arrived too early and no later event re-triggers it.

**Symptom.** A feature that works when activated after the actor exists and does
nothing when activated before, or the reverse — order-dependent, and the order
differs between the editor and a packaged run.

**Detect.** List which events each handler responds to:

```bash
rg -n -A12 "HandleActorExtension|FExtensionHandlerDelegate" --glob "*.cpp" . \
  | rg "EventName ==|NAME_"
```

A handler that responds only to the generic added/removed events, with no
semantic ready event, is the finding. The correct shape in the measured reference
dispatches on both: the generic event *and* a named readiness event such as
"abilities ready" or "bind inputs now", so whichever arrives second does the work.

**Guardrail.** Handlers accept both the generic event and a semantic readiness
event, making activation order irrelevant. Emitting a new readiness event costs a
name and one call — it requires no change to the feature infrastructure.

---

### MG-16 - Receiver registration written by hand and left incomplete

**Mechanism.** Actors register with the component manager in three places: add
receiver early, send a ready event at begin play, remove receiver at end play.
Classes inheriting a modular base get all three. Classes that do not inherit it
have them written by hand.

**Why it is silent.** Missing the removal leaks a registration whose owner is
gone. Weak references prevent a crash; the record remains. Missing the ready
event means features silently never attach to that actor class.

**Why the obvious check misses it.** The class works. It renders, it ticks, it
does its job. The two or three lines that make it visible to features are
infrastructure boilerplate, and boilerplate absent from a file looks like
boilerplate that was not needed there.

**Symptom.** A feature attaches to every actor class except one, with no error —
or registrations that accumulate across level transitions.

**Detect.** Compare the three calls per class:

```bash
rg -l "AddGameFrameworkComponentReceiver" --glob "*.cpp" . > /tmp/add
rg -l "RemoveGameFrameworkComponentReceiver" --glob "*.cpp" . > /tmp/rem
comm -23 <(sort /tmp/add) <(sort /tmp/rem)
```

Any file that adds and never removes is the finding. In the measured reference
one HUD class inherits a non-modular engine base and therefore carries all three
calls by hand — correctly, but by hand, which is the fragile arrangement.

**Guardrail.** Put the three calls in a base class and inherit it. Where that is
impossible, add a test that asserts the receiver count returns to baseline after a
level transition.

---

## Composition

### MG-17 - Handle dropped without realising it was the unsubscribe

**Mechanism.** Extension handler and component requests return reference-counted
handles. There is no explicit removal API — releasing the last reference *is* the
removal.

**Why it is silent.** Keeping a handle costs nothing visible, and dropping one
produces no event. Both directions of the mistake are quiet: holding too long
leaks a subscription, releasing too early silently detaches a live feature.

**Why the obvious check misses it.** Nothing in the calling code says
"unsubscribe". Reviewing teardown for removal calls finds none — correctly, because
there are none — and it takes knowing the ownership model to recognise that
emptying an array of handles is the teardown.

**Symptom.** Either features that cannot be removed, or features that detach when
an unrelated container is cleared.

**Detect.** Confirm every handle-producing call has a stored destination:

```bash
rg -n "AddExtensionHandler|AddComponentRequest" --glob "*.cpp" . -A3 \
  | rg -v "\.Add\(|=\s*\w+\.Add"
```

A call whose result is not stored is a subscription that ends immediately.

**Guardrail.** Name the container for what it does — a handle array is an
ownership ledger, not a cache — and comment at its declaration that clearing it is
the unsubscribe operation.

---

### MG-18 - Plugin activation order assumed

**Mechanism.** Plugin URLs from an experience and from each of its action sets
merge into one list and activate in parallel. Action *execution* order is
deterministic; plugin *activation* order is not.

**Why it is silent.** Parallel activation usually completes before anything
depends on the result, and when it does not, the dependent code has its own
readiness check that eventually passes.

**Why the obvious check misses it.** Action ordering *is* deterministic and
documented — experience actions first, then action sets in order. Having verified
that, it is natural to assume the same of plugins, and nothing contradicts it.

**Symptom.** A feature that depends on another plugin's registration works
consistently until content or load timing changes.

**Detect.** Check whether the plugin list is loaded as a batch:

```bash
rg -n -A10 "GameFeaturePluginURLs" --glob "*.cpp" . | rg "for\s*\(|LoadGameFeaturePlugin"
```

A loop issuing loads without sequencing between them means order is not
guaranteed.

**Guardrail.** Express cross-plugin dependencies as readiness states rather than
activation order. If ordering is genuinely required, sequence the loads and say
why in the code.

---

## Failure handling

### MG-19 - Asynchronous deactivation counted but not honoured

**Mechanism.** The deactivation context supports pausers for asynchronous
teardown. The implementation counts them and, if any are outstanding, logs an
error and proceeds.

**Why it is silent.** It is not entirely silent — it logs. But it logs and
*continues*, so teardown completes and the sequence appears successful. A log line
during shutdown competes with everything else logged during shutdown.

**Why the obvious check misses it.** The support looks present: the context is
constructed with a pauser callback, the count is tracked, the branch exists.
Reviewing for "is async deactivation handled?" finds all the machinery. Reading
what the branch *does* is a separate step.

**Symptom.** An action with asynchronous teardown is cut short. Whatever it was
waiting to release stays held, and the failure is attributed to whichever
subsystem later notices the leak.

**Detect.** Find pauser handling and read the branch:

```bash
rg -n -A8 "NumExpectedPausers|DeactivatingContext" --glob "*.cpp" . \
  | rg "UE_LOG|Error|return|check"
```

An error log with no wait and no abort is the finding. The measured reference
states its own limitation in the log text — that asynchronous deactivation is not
fully supported — which makes it a documented gap rather than an unknown one.

**Guardrail.** Either wait for pausers before completing teardown, or reject
actions that request asynchronous deactivation at validation time. Logging and
continuing converts a design gap into a runtime one.
