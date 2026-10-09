---
name: ue-asset-loading-and-memory
description: >-
  Design or audit asset loading and CPU memory residency in Unreal Engine: the
  asset manager and primary asset identifiers, asset bundles and cook rules,
  hard versus soft versus weak reference semantics, streamable handle ownership,
  synchronous load hitches, startup job sequencing, garbage-collection
  reachability, retention leaks and unload paths. Use when reducing load times
  or memory, choosing reference types, adding content-pulling definitions,
  diagnosing hitches, or investigating objects that are never collected.
---

# UE asset loading and CPU memory

The invariant:

> An asset stays in memory because something reachable **owns** it. Loading is a
> policy decision; residency is an ownership fact. They are set by different code
> and must be reviewed separately.

Measured patterns from a reference product: [patterns](references/patterns.md).
Detection recipes: [failure modes](references/failure-modes.md).

Related skills: `ue-data-driven-architecture`, `ue-modular-gameplay`,
`ue-streaming-and-platform-budgets`, `ue-runtime-allocation-and-caching`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Separate the five budgets before optimizing anything

| Budget | What it is | Measured by |
|---|---|---|
| A. Disk / cook | package bytes shipped | build size, chunk sizes |
| B. CPU memory | object graph plus bulk data | memory report, object list |
| C. GPU memory | live render resources | platform GPU profiler |
| D. Streaming pool | a **limit**, not consumption | streaming stats |
| E. Net objects | actors, channels, bandwidth | network profiler |

This skill owns A and B. C and D belong to
`ue-streaming-and-platform-budgets`; E to `ue-runtime-allocation-and-caching`.

**The most common analytical error is treating D as B.** A pool setting grants
permission to use memory. It never reports use.

---

## 2. Reference semantics decide load cost

Three mechanisms, routinely conflated:

| Mechanism | Effect |
|---|---|
| reflected property, manual reference collection, a retained streamable handle | **owns** — keeps resident |
| weak pointer, object key | **observes** — keeps nothing |
| soft object or class pointer | **a path, not a reference** |

The third line is where most reasoning fails. **A soft pointer saves nothing by
itself.** Residency is decided by where the loaded result is stored — a soft
reference resolved into a reflected property is a hard reference with extra
steps.

### Measure the transitive closure, not the direct count

Direct reference counts are misleading. What matters is how many packages load
when this one loads. In the audited reference the same architectural layer
spanned three orders of magnitude depending on reference type alone: an archetype
holding hard references pulled over a thousand packages, while a catalog entry
addressing by identifier pulled two.

That single contrast is the argument for treating reference type as
architecture rather than style. Recipe: AL-01.

### Choosing

| Need | Reference |
|---|---|
| address before load; cook and bundle identity | primary asset identifier |
| optional, feature-scoped or async content | soft object or class pointer |
| required whenever the owner is loaded, and small | hard pointer |
| data selects an implementation class | class reference |
| owner-exclusive polymorphic fragment | instanced object |

Rule of thumb: a definition that is a **catalog entry** references by identifier
or softly; a definition that is an **archetype** may reference hard — but its
closure must be measured and budgeted, not assumed.

---

## 3. Bundles express role, not grouping

Declare the load role beside the reference, then request bundles per runtime role
at load time.

Gates:

- every soft reference carries an intentional bundle tag;
- server-irrelevant presentation is client-only;
- prediction-relevant gameplay classes are client and server;
- **a missing bundle tag means "always loaded with the owner"** — decide it, do
  not default into it;
- cook rules control budget **A**, never budget **B**.

A label asset with thousands of soft references and no hard references determines
what ships and retains nothing at runtime. Do not read cook rules as residency.

Watch for a declared bundle name that no property ever uses: it is requested at
load time, matches nothing, and looks like a working tier. Recipe: AL-02.

---

## 4. Startup discipline

### Never synchronously load a graph you have not measured

The dominant boot hitch in a data-driven project is one synchronous load whose
hard closure is large. An elegant async bundle pipeline that runs *after* it is
decoration.

- [ ] every synchronous load on the boot path is justified;
- [ ] its transitive closure is measured, not assumed;
- [ ] an async alternative was considered, with an explicit wait state;
- [ ] the loading screen carries a reason string;
- [ ] cancellation is distinguishable from completion.

### Startup jobs must own handles and report truthfully

A progress bar that never moves is a bug, not a cosmetic issue — it hides which
job is slow. Three independent layers can each break it: a macro that never
fills the handle, a throttle comparison with swapped operands, and an empty
progress receiver. Any one of them is enough. Recipe: AL-03.

### Global data assets need bundles too

Soft class pointers on a globally-loaded data asset with **no** bundle tags load
synchronously at first use — typically in the frame of first damage. Tag them and
preload them with the mode. Recipe: AL-04.

---

## 5. Retention: what actually keeps objects alive

Audit six owners explicitly: reflected containers on long-lived subsystems;
manual reference collection in native code; retained streamable handles; delegate
bindings capturing strong references; component and actor ownership chains; class
default objects reached through class references.

### A convenience loader must not default to permanent

The worst shape in this area is a helper that loads an asset and adds it to a
reflected set, with the keep-in-memory parameter **defaulting to true** and no
release API anywhere. Every casual call then synchronously loads *and permanently
roots* the asset. The soft pointer was chosen for deferred loading; the API turns
it into a process-lifetime hard reference.

Required design: the flag is explicit at every call site or defaults to false; a
paired release exists and is used; the retained set is inspectable from a console
command; retention has an owner and a scope. Recipe: AL-05.

### Strong keys pin object graphs — and raw pointers lose them

```text
map<strong actor pointer, strong value>   one missed unregister pins the actor,
                                          its meshes, materials, sounds, effects

map<raw actor pointer, non-reflected struct of object pointers>
                                          garbage collection cannot see the
                                          values; the key can dangle
```

Both errors can coexist in one codebase. **Audit direction as well as presence.**
Prefer object keys with explicitly-owned values plus a periodic prune. Recipe:
AL-06.

---

## 6. Unloading must exist before you claim modularity

If a project cannot answer "what is released when a mode ends", its memory
profile only grows. Either implement release, or state plainly that mode changes
require map travel — that is a legitimate scope decision, and leaving it
undefined is not.

The measurement is blunt and takes one command: count unload calls, bundle
releases and explicit collection requests across the whole project. In the
audited reference every one of those counts was **zero**. Recipe: AL-07.

### Avoid collection ping-pong

A forced collection at a transition boundary must not collect what the next
transition immediately needs. Options: keep transition-critical classes rooted,
defer collection past the next load, or do not force it and let the budget drive
it.

---

## 7. Failure handling changes memory behaviour

- a cancelled load must not run the success path;
- asynchronous results must be read, not discarded;
- partially loaded state must be releasable;
- waiting without a timeout converts a stall into a hang;
- a permanent loading screen with no reason string is not error handling.

The sharpest instance: binding the cancel delegate to the **same callback** as
completion. A cancelled load then reports success, downstream code dereferences
unloaded assets, and each of those dereferences is individually silent. Recipes:
AL-08, AL-09.

---

## 8. Review checklist

### References

- [ ] reference type chosen per lifecycle and documented in metadata;
- [ ] transitive hard closure measured for every archetype-level definition;
- [ ] no soft reference resolved into an unbounded reflected cache;
- [ ] bundle tags on all soft references, and every requested bundle is used;
- [ ] cross-plugin edges intentional and acyclic.

### Loading

- [ ] no unmeasured synchronous load on boot or in a hot path;
- [ ] async loads own their handles and can be cancelled;
- [ ] progress reporting is verified to move, not merely implemented;
- [ ] cancellation and failure paths are distinct from success;
- [ ] global data assets are bundled, not lazily loaded at first use.

### Retention

- [ ] every long-lived container has an owner, a bound and a prune policy;
- [ ] strong keys justified; object keys used where identity suffices;
- [ ] non-reflected object pointers eliminated or documented as weak by design;
- [ ] register and unregister pairs verified across teardown paths;
- [ ] a release API exists for anything deliberately kept resident.

---

## 9. Measurement plan

Static first — it is cheap and finds structural problems:

1. build the dependency graph from the asset registry: direct hard and soft
   counts, transitive hard closure per definition, cross-plugin edges;
2. rank definitions by closure and compare against their architectural layer;
3. search for synchronous loads on boot and hot paths;
4. inventory retention owners by type.

Runtime, once a packaged build exists: memory reports before and after a mode
cycle; object listings on suspected roots — root-graph evidence, not process
memory; fifty to a hundred spawn and travel cycles looking for monotonic growth;
an allocation profiler for attribution.

### Do not measure residency in the editor

Editor builds commonly load **both** client and server bundles, so an in-editor
memory profile represents neither shipping role. Residency numbers require a
packaged build; use the editor for relative structural comparison only. Recipe:
AL-10.

---

## 10. When to stop

Optimize loading and residency when boot or transition time is a product problem,
a platform ceiling is real and near, growth is monotonic across a session, or a
specific closure is measurably oversized.

Do not restructure references on aesthetics. A fourteen-package closure is not a
problem; a thousand-package synchronous closure on the boot path is. Measure
first, and **keep the measurement** so the next change can be compared against
it.

---

## Provenance

The findings come from a source and dependency-graph audit of Epic's Lyra Starter
Game on Unreal Engine 5.6. The engine's own asset manager and streamable manager
are not part of that project, so every claim about their internals is inferred
from call sites and marked as such rather than presented as measured.

No profiler was run and no timing was captured: this material is structural by
construction, and it deliberately contains no performance numbers. What it
contains is counts — of call sites, of unload paths, of packages in a closure —
which is a different kind of evidence and a more portable one.

Source addresses stay in the research archive. Each entry carries a stable
identifier (`AL-01` and up) resolving back to the audited location there.

## Evidence boundary

One project, one engine version. Binary assets were not read, so the contents of
any specific closure are structural rather than byte-measured. Re-run the recipes
against your own tree; the counts quoted show the shape of a contrast, not a
target.
