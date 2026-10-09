# Patterns: asset loading and residency in a measured reference

A worked reading of one shipped project's loading path, from asset-manager
startup to feature-plugin activation, audited as source.

Individual defects are in [failure modes](failure-modes.md) with detection
recipes. This file is about the shape: which decisions determine load cost, which
determine residency, and why those are two different reviews.

Markers: **[measured]** — read in source or config; **[derived]** — conclusion
from measured facts; **[open]** — not answerable without a packaged build or
engine source, and left open.

---

## 1. The five budgets, and the one that is not a budget

| Budget | What it is | Measured by |
|---|---|---|
| A. Disk / cook | package bytes shipped | build and chunk sizes |
| B. CPU RAM | object graph plus bulk data | memory report, object list |
| C. GPU VRAM | live render resources | platform GPU profiler |
| D. Streaming pool | **a limit, not consumption** | streaming stats |
| E. Net objects | actors, channels, bandwidth | network profiler |

This skill owns A and B.

**The most common analytical error in this area is reading D as B.** A pool
setting grants permission to use memory. It never reports use, it never causes
use, and lowering it does not free anything that is already resident.

---

## 2. Reference type is the largest single lever

Three mechanisms, routinely conflated:

| Mechanism | Effect |
|---|---|
| a reflected property, an explicit GC reference, a retained load handle | **owns** — keeps resident |
| a weak pointer, an object key | **observes** — keeps nothing |
| a soft pointer | **a path, not a reference** |

The third line is where reasoning usually fails. A soft pointer saves nothing by
itself. Residency is decided by **where the loaded result is stored** — and a
soft reference resolved into a strong property is a hard reference with extra
steps.

### The measured spread

From the dependency graph of the audited project — 3 874 packages, 16 639 hard
edges, 9 333 soft edges **[measured]**:

| Asset | Packages pulled by loading it |
|---|---:|
| pawn archetype with a hard class-and-object chain | **1 015** |
| weapon pickup definition | 800 |
| ability set | 121 |
| input config | 14 |
| action set referencing by identifier and soft pointer | **2** |
| playlist referencing by primary asset identifier | **2** |

**[derived]** Three orders of magnitude, from one decision made per property.
That is the whole argument for treating reference type as architecture rather
than as style — and the reason a "make it soft" refactor has to start from the
closure measurement rather than from the property list.

### Choosing

| Need | Reference |
|---|---|
| address before load; cook and bundle identity | primary asset identifier |
| optional, feature-scoped or async content | soft object or class pointer |
| required whenever the owner is loaded, and small | hard pointer |
| data selects an implementation class | class reference |
| owner-exclusive polymorphic fragment | instanced object |

Rule of thumb: a definition that is a **catalog entry** references by identifier
or soft pointer; a definition that is an **archetype** may reference hard, but its
closure must be measured and budgeted.

---

## 3. Bundles declare role, and their absence declares nothing

Put the load role beside the reference:

```cpp
UPROPERTY(EditAnywhere, meta=(AssetBundles="Client"))
TSoftClassPtr<UUserWidget> WidgetClass;

UPROPERTY(EditAnywhere, meta=(AssetBundles="Client,Server"))
TSoftClassPtr<UGameplayAbility> AbilityType;
```

Then request bundles per runtime role at load time.

**[measured]** In the audited project the bundle vocabulary is small — client
and client-plus-server annotations only — and one declared bundle name is
requested on every load while appearing on **no** property in source at all. It
is either satisfied entirely by content, or it is dead. **[derived]** A bundle
name that no property claims is indistinguishable from a typo, and neither the
compiler nor the cooker will say which it is.

Gates worth adopting:

- every soft reference has an intentional bundle annotation;
- server-irrelevant presentation is client-only;
- prediction-relevant gameplay classes are client-and-server;
- a missing annotation means "loaded whenever the owner loads" — decide it, do
  not default into it;
- cook rules control budget A, not budget B. A label asset with thousands of
  soft references and no hard ones determines what ships and retains nothing.

---

## 4. Startup: the shape that works, and the shape that only looks like it

The audited project has a well-formed startup-job framework **[measured]**: named
jobs, weights, per-job timing logs, a progress delegate, and boot-timing scopes
that integrate with the engine's trace.

**[measured]** It also has: a macro that never fills the load handle it is
designed to return, a progress throttle whose comparison can never be true, and a
progress receiver whose body is a comment.

**[derived]** Three independent layers, each individually harmless, combining
into a startup with no progress reporting at all — inside a framework built to
report it. This is the single most instructive thing in the audit, and the
general form is worth memorizing: **scaffolding is not evidence of function.**
Recipes: AL-02, AL-03.

What to take from it anyway:

- **name every startup job and log its duration.** Per-job timing is nearly free
  and it is the only thing that answers "what is slow at boot".
- **wrap boot phases in the engine's timing scopes**, so the data lands in the
  same trace as everything else.
- **fail fatally on genuinely required global data.** The audited project does
  this for its global data asset, with a comment explaining that a soft failure
  here would be harder to diagnose than a hard one **[measured]**. That is the
  correct call, and it is rare.

---

## 5. The synchronous load that dominates everything else

**[measured]** The root definition of a game mode is resolved with a synchronous
load in the game thread, and its own authors marked it for async conversion.
That definition holds a hard pointer to a pawn archetype, which holds hard
references to the pawn class, its ability sets, its input config, its tag policy
and its camera mode — all hard.

**[derived]** One line therefore pulls the closure measured at over a thousand
packages, **before** the elegant asynchronous bundle pipeline underneath it runs
at all. An async pipeline that executes after the bulk of the work is decoration.

The general lesson is a review question rather than a rule: *for every
synchronous load on a boot or transition path, what is its transitive closure?*
If nobody has measured it, the loading architecture is unverified regardless of
how much of it is asynchronous.

**[measured]** Note the asymmetry that makes this easy to miss: on a client the
same definition arrives by replication and is resolved by the net driver, so the
synchronous cost exists on one side only, and profiling the wrong side finds
nothing.

---

## 6. Handle ownership: the difference between loading and controlling

**[measured]** In the audited experience loader, every load handle is a local
variable. The component stores none of them.

**[derived]** Three consequences, none of which produce an error:

1. **Cancellation is impossible.** If the mode changes or the world dies mid-load,
   there is no reference to cancel.
2. **Release is impossible.** Residency is held inside the asset manager rather
   than by the component, and unloading requires the API that nothing in the
   project calls.
3. **The load survives only incidentally** — because the completion delegate is
   bound to the handle and the streamable manager keeps it alive until it fires.

**[measured]** The same codebase contains the correct discipline elsewhere: UI
async actions cancel their handles on teardown, and an async helper mixin cancels
in its destructor. The pattern was known; it was not applied at the place with the
largest closure.

**Take the shape from the UI code, not from the loader.**

---

## 7. Retention: six owners, audited by name

Anything that stays resident is held by one of:

1. reflected containers on long-lived subsystems;
2. explicit GC references added by native code;
3. retained load handles;
4. delegate bindings capturing strong references;
5. component and actor ownership chains;
6. class default objects reached through class references.

### The convenience loader that defaults to permanent

**[measured]** A helper resolves a soft pointer, and a boolean parameter
defaulting to **true** adds the result to a reflected set. There is no removal
API, no call passing false, and no clearing anywhere in the project.

**[derived]** Every casual call therefore loads synchronously *and* roots the
asset for the lifetime of the process. The soft pointer was chosen to defer
loading; the helper converts it into a permanent hard reference at the call site,
invisibly, by default.

The design that avoids it: make retention explicit at the call site or default it
to false, provide a paired release, make the retained set inspectable from a
console command, and give retention an owner and a scope rather than assigning it
to "the asset manager". Recipe: AL-05.

### Both directions of the pointer error

Strong keys pin more than intended — a map keyed by actor pointers keeps every
key actor and its whole presentation graph alive on one missed unregister.

Raw pointers in a non-reflected struct do the opposite: the collector cannot see
them, so the values can be collected while referenced and the keys can dangle.

**[derived]** Both errors appear in real codebases, sometimes in the same one.
Audit *direction*, not just presence.

---

## 8. Unloading, or the six "never"s

**[measured]** In the audited project, searched across all source:

| Mechanism | Occurrences |
|---|---:|
| primary asset unload | 0 |
| bundle removal | 0 |
| explicit collection | 0 |
| async flush | 0 |
| memory trim | 0 |

The one forced collection in the project is in the loading-screen hide path
**[measured]**, and the experience loader's own teardown carries a comment
admitting it deactivated without unloading **[measured]**.

**[derived]** The residency table for this project has "never" in the release
column for six of its rows. For a session-based game restarted between matches
that is an acceptable engineering position. For a service title that swaps modes
in place it is not — and the difference is a product decision that must be made
explicitly rather than discovered from a memory graph.

**The honest options are two:** implement release, or state plainly that mode
changes require travel. What does not work is claiming runtime modularity while
the release column is empty.

### Watch for collection ping-pong

**[measured]** Hiding the loading screen forces a full purge; showing it again
synchronously loads the widget class that purge just collected. A forced
collection at a transition boundary must not collect what the next transition
immediately needs. Context: AL-07.

---

## 9. Failure handling is a memory concern

- a cancelled load must not run the success path;
- the result of an asynchronous activation must be read;
- partially loaded state must be releasable;
- an unbounded wait converts a stall into a hang;
- a loading screen with no reason string is not error handling.

**[measured]** In the audited project the cancel delegate invokes the *same*
callback as completion, and the plugin-activation result parameter is never read.
**[derived]** A cancelled or failed load therefore transitions to "loaded", and
downstream code resolves soft references that are not there — where, by design,
a failed resolve is silently skipped. The result is graceful degradation with no
diagnostic, which is the most expensive kind.

### One tool worth copying outright

**[measured]** The project ships console variables that inject artificial delay
into mode loading. That is a reproducible way to exercise slow-load and
cancellation paths without a network or a cold cache, and almost nobody builds
one.

---

## 10. Measurement plan

Static first, because it is cheap and finds structural problems:

1. build the dependency graph from the asset registry: direct hard and soft
   counts, transitive hard closure per definition, cross-plugin edges;
2. rank definitions by closure and compare against their architectural layer —
   a catalog entry with a large closure is the finding;
3. search for synchronous loads on boot and hot paths;
4. inventory retention owners by type (§7).

Runtime, once a packaged build exists:

- memory reports before and after a full mode cycle;
- object lists and reference queries on suspected roots — root-graph evidence,
  not process memory;
- fifty to a hundred spawn, despawn and travel cycles, looking for monotonic
  growth;
- allocation attribution from the engine's profiler;
- the allocator's dangling-pointer mode when corruption is suspected.

### Do not measure residency in the editor

**[measured]** Editor builds can load **both** role bundles, by an explicit
editor branch in bundle selection — a fact the project's own comments
acknowledge, noting the resulting hitches.

**[derived]** An in-editor memory profile therefore represents neither shipping
role. Use it for relative structural comparison only; absolute residency requires
a packaged build.

---

## 11. When to stop

Optimize loading and residency when boot or transition time is a product problem,
when a platform memory ceiling is real and near, when growth is monotonic across
a session, or when a specific closure is measurably oversized.

Do not restructure references on aesthetics. A fourteen-package closure is not a
problem. A thousand-package synchronous closure on the boot path is. Measure
first, and keep the measurement, so the next change has something to be compared
against.

---

## Provenance

The analysis and every number above come from a source and configuration audit of
Epic's Lyra Starter Game on Unreal Engine 5.6, plus a dependency graph extracted
from its asset registry through the editor.

Two boundaries applied to that reading and bound these claims: the engine's own
asset manager, streamable manager and feature subsystem are not part of the
project, so statements about their internals are inference from call sites rather
than from source; and no profiler was run, so there are no timing or
memory-footprint numbers here by construction — the package counts are static
graph measurements.

Source addresses stay in the research archive that produced this skill. Entry
identifiers in [failure modes](failure-modes.md) resolve back to the audited
locations, so any specific claim can be produced on request.

## Evidence boundary

One project, one engine version, one workspace. The structure is transferable;
the specific defects are evidence, not guarantees about other versions. Re-run
the detection recipes against your own tree before acting on any specific claim.
