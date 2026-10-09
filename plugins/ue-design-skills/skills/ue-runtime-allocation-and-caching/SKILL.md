---
name: ue-runtime-allocation-and-caching
description: >-
  Design or audit runtime allocation, pooling, caching and replication cost in
  Unreal Engine: per-frame and per-event churn, object pools, bounded caches and
  ring buffers, pointers into container storage, strong versus weak retention of
  spawned components, fast-array and subobject replication, dormancy and
  relevancy, and dedicated-server exclusions. Use when profiling hitches,
  investigating memory that grows during a session, effect or UI churn, or
  deciding how to reduce replicated object count.
---

# UE runtime allocation and caching

The invariant:

> Every cache needs an owner, a bound and an eviction rule. Every pooled object
> needs a stable handle. Every replication optimization must name which cost it
> reduces — memory, CPU or bandwidth — because they are not the same.

Measured patterns from a reference product: [patterns](references/patterns.md).
Detection recipes: [failure modes](references/failure-modes.md).

Related skills: `ue-asset-loading-and-memory`, `ue-cosmetics-and-teams`,
`ue-gameplay-messaging`, `ue-streaming-and-platform-budgets`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Never store a raw pointer into a container's storage

This is the highest-severity defect class in this skill, and it is the one that
looks most harmless:

```cpp
FPooledList& Pool = PooledMap.FindOrAdd(Key);       // address of a map value
LiveEntries.Emplace(Component, &Pool, ReleaseTime); // held across frames
```

Maps and arrays reallocate on insertion. A later insert invalidates every stored
address. The failure is **data-dependent**: it needs a second key inserted while
an earlier entry is still live, so it survives casual testing and appears under
load.

A null check does not help. The pointer is not null; it is non-null garbage.

### Rules

- store a **key or an index**, and resolve at the point of use;
- if a stable address is genuinely required, use a container that guarantees
  stable element addresses, and say so in a comment at the declaration;
- treat "pointer obtained from a container, stored beyond the current scope" as a
  review blocker, not a style note;
- when you suspect one, the allocator's stomp mode converts a probabilistic
  corruption into a deterministic crash at the right line.

The same shape appears with lazily-growing statistics maps whose entries are
cached by a widget and dereferenced every frame — the map grows a key when a new
data source appears, and the widget's pointer dies mid-session. Recipes: RC-01,
RC-02.

---

## 2. Bound every cache and name its eviction

A cache without a bound is a leak with good intentions. For each one, write down:

```text
owner            who invalidates it
key space        bounded by what?
capacity         a number, or "unbounded" with a justification
eviction         time, count, or explicit removal
retention        strong or weak
teardown         what empties it, and when
```

Three shapes recur and each is silent:

**Read-modify-write growth.** Fetch a collection, append one element, write the
whole thing back. Per-event cost grows linearly and total work is quadratic over
a session — and if nothing ever clears it, the collection is also a leak. Recipe:
RC-03.

**Re-append without pruning.** A component that re-adds every previously spawned
effect on each trigger and never removes finished ones. When the arrays are
strong references, every one-shot effect is pinned for the whole match. Recipe:
RC-04.

**Prefilled buffers reported as data.** A fixed-capacity sample cache filled with
zeroes reports a misleading minimum and average until it wraps. Track the fill
count, or exclude the prefix. Recipe: RC-08.

---

## 3. Pools need a lifecycle, not just reuse

A pool is correct when acquire and release are symmetric and idempotent; released
objects are reset to a known state; there is a high-water policy — grow, cap, or
trim on idle; pooled objects remain reachable by the collector while pooled; the
pool empties on teardown; and a leaked acquire is detectable rather than silent.

Fixed-size pools must define what happens on exhaustion: block, drop, or grow.
Silent drop is acceptable for cosmetic effects only, and it should be counted.

**A pool that only grows is not a leak in the technical sense and behaves like one
in practice.** One burst leaves its peak allocated for the rest of the session.

---

## 4. Churn: diff, do not rebuild

A periodic scan that destroys and recreates its descriptor objects every interval
allocates, invalidates observers, and hides real changes in noise.

```text
compute the desired set
diff against the current set
add new, remove missing, leave the rest alone
```

Reserve capacity once when the size is predictable. In hot paths prefer the
reset-without-freeing operation over the one that releases the buffer — the
latter guarantees a reallocation on the next frame. Do not allocate in paint or
per-frame render-thread paths at all. Recipes: RC-05, RC-06, RC-07.

---

## 5. Protocol identifiers need width and uniqueness discipline

A batch identifier assigned as *the current in-flight count* rather than a
monotonic sequence produces reuse: A gets 0, B gets 1, A confirms and is removed,
C gets 1 again — and a handler that matches the first plausible entry applies the
confirmation to the wrong batch.

Compounding it, the same value can be one width at the source, another in the
message and a third in storage — which turns a wraparound into a permanent
mismatch, and an unbounded pending list into an unbounded leak.

### Rules

- identifiers are sequences, never counts;
- one width for the whole path, asserted at every boundary;
- define wrap behaviour explicitly;
- handlers match on identity, not on "the first entry that could be it";
- an unbounded pending list needs a timeout and a drain policy.

Recipe: RC-09.

---

## 6. Replication: name the axis you are optimizing

Three different costs, routinely conflated:

| Mechanism | Memory | CPU | Bandwidth |
|---|---|---|---|
| Dedicated-server presentation exclusion | ↓ | ↓ | **unchanged** |
| Fast-array delta serialization | **↑** per-item key and per-connection state | **↑** delta walk | ↓ |
| Subobject replication | ↓ | ↓ | ↓ |
| Dormancy | — | ↓↓ | ↓ |
| Relevancy and replication graph | — | ↓↓ | ↓ |

Two counterintuitive facts worth internalizing:

- excluding cosmetics on a dedicated server saves memory and CPU and changes
  bandwidth by **zero**, because the intent list still replicates;
- fast arrays are a **bandwidth** optimization that costs memory and CPU.

The genuine object-count reducer is subobject replication: N owned items add zero
actors and zero channels.

### Before claiming a replication optimization

- [ ] state which axis improves and which regresses;
- [ ] measure that axis specifically, not "performance";
- [ ] confirm the mechanism is actually **enabled** rather than merely present —
      see `ue-multiplayer-authority` for a measured case where the replication
      graph ships disabled, dormancy is unused, and a force-update list is
      declared, read, and never populated;
- [ ] verify net-mode gating is consistent across presentation systems;
- [ ] check replicated history structures for a removal path.

---

## 7. Dedicated-server exclusions must be systematic

List every client-only construction and guard it in one reviewable place:
cosmetic actors and meshes, widgets and layouts, effect and audio components,
preview and capture systems, input and settings objects.

**An inconsistent set is worse than none**, because server memory profiles become
unpredictable — one system guarded while a sibling spawning real actors is not.
Audit by searching for the net-mode guard and diffing against the list of
presentation systems.

---

## 8. Review checklist

### Allocation

- [ ] no stored pointers into container storage;
- [ ] hot paths reset rather than free, with capacity reserved;
- [ ] no allocation in paint or render-thread paths;
- [ ] periodic work diffs rather than rebuilds.

### Caches and pools

- [ ] owner, bound, eviction and teardown written down for each;
- [ ] key space provably bounded;
- [ ] retention strength intentional;
- [ ] acquire and release symmetric; exhaustion policy defined;
- [ ] prefilled buffers do not distort statistics.

### Protocol

- [ ] identifiers are sequences with one consistent width;
- [ ] pending lists have a timeout and a drain;
- [ ] handlers match by identity.

### Replication

- [ ] the optimization names its axis;
- [ ] the mechanism is verified enabled;
- [ ] net-mode gating consistent across presentation systems;
- [ ] replicated history bounded.

---

## 9. Measurement plan

- **long-session soak**: fifty to a hundred spawn, despawn and transition cycles,
  looking for monotonic growth rather than an absolute number;
- per-frame allocation counters in the hot scenes;
- the allocator's stomp mode **first** when a dangling-pointer class is
  suspected — it is a binary answer, and it costs one run;
- profiler counters for boundedness curves over time, which is the cheapest way
  to turn "is this cache bounded?" into a graph;
- network statistics and a network profiler for the replication axes, measured
  separately from each other;
- server and client measured independently; never generalize one to the other.

**Report growth curves, not single samples.** A cache that is 4 MB after one
minute and 40 MB after ten is a defect regardless of where it eventually stops.

---

## Provenance

The patterns and failure modes in `references/` come from a source audit of the
runtime, feedback, UI and weapon systems of Epic's Lyra Starter Game on Unreal
Engine 5.6, read as source rather than profiled. No profiler was run, so there
are no timing numbers here by construction — the findings are structural, and the
recipes tell you how to measure them yourself.

Source addresses stay in the research archive that produced this skill. Each
entry carries a stable identifier (`RC-01` and up) that resolves back to the
audited location, so any specific claim can be produced on request.

## Evidence boundary

One project, one engine version, one workspace. The defect classes are general;
the specific instances are evidence, not guarantees about other versions. Re-run
the detection recipes against your own tree before acting on any specific claim.
