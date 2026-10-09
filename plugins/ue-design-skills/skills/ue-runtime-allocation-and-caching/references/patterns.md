# Patterns: runtime allocation and caching in a measured product

A worked reading of the runtime allocation, pooling, caching and replication-cost
surface of one shipped project.

This file differs from the others in one respect worth flagging: **two of its
findings are memory-safety defects, not design smells.** Everywhere else in this
bundle the failures are silent-but-benign until adopted. Here, two of them are
dangling pointers in shipping paths, and they are silent for the ordinary reason —
freed memory usually still contains the right bytes.

Markers: **[measured]** — read in source; **[derived]** — conclusion from measured
facts; **[open]** — requires a runtime experiment.

**Nothing here was profiled.** Every claim is structural. That is a limitation
and also the point: both critical findings were found by reading, and both are
confirmable in one run under an allocator that poisons freed pages.

---

## 1. The same defect twice, in two unrelated subsystems

A raw pointer taken from a container's storage and held across frames. It appears
independently in a cosmetic feedback pool and in a statistics cache
**[measured]**.

**Case one — the pool.** A map from mesh to a pooled component list. Code takes a
reference to a map value, stores its address in a live-entry struct, and
dereferences it up to a second later when the entry expires **[measured]**.

**Case two — the statistics cache.** A map from statistic type to a fixed-size
sample cache. A getter returns the address of a map value; a Slate widget stores
that pointer as a member and dereferences it **every frame during paint**
**[measured]**.

**[derived]** Both are correct until the map rehashes, and both maps grow after
the pointer is taken:

- the pool map gains a key the first time a second visual style appears — mixed
  normal and critical damage within one second is enough;
- the statistics map is **populated lazily**, gaining keys as a game state
  appears, a player state appears, a network connection appears, and a latency
  module is enabled **[measured]**. A widget that cached a pointer before any of
  those events is holding a stale address afterwards.

The second case is worse in a specific way: the dereference happens in a paint
path that the widget declares as always volatile, so it runs every frame with no
invalidation mechanism **[measured]**.

**[derived]** The general rule this yields is worth more than the two instances:
**a pointer obtained from a container and stored beyond the current scope is a
review blocker, regardless of how the container is used.** Store a key or an
index and resolve at use. The audited code even guards one of them with a
non-null check, which cannot detect this failure — the pointer is non-null
garbage. Recipes: RC-01, RC-02.

---

## 2. Unbounded growth, three shapes

| Shape **[measured]** | Where | What it costs |
|---|---|---|
| Read whole array, append one, write whole array back — never cleared | damage number effect data | Linear per event, quadratic per session, two full copies per hit |
| Re-append every previously active component on each trigger, never prune finished ones | footstep and impact effects | Strong references pin every one-shot sound and effect for the whole match |
| Pending protocol entries removed only on a matching confirmation | hit-marker batches | Grows without bound once matching stops working (§4) |

**[derived]** The first two share a structure that is easy to miss in review: the
code that grows the collection is also the code that appears to manage it. Reading
`Empty()` followed by `Append()` looks like a refresh. It is a refresh that
re-adds everything, and the array is a strong property, so nothing is ever
released.

The second one also uses `Empty()` rather than `Reset()` in a path that runs at
footstep frequency **[measured]**, which frees the buffer and guarantees a
reallocation on the next call — a smaller problem sitting inside a larger one.
Recipes: RC-03, RC-04, RC-06.

---

## 3. Pools without lifecycle

The component pool grows to the peak concurrent count and **never shrinks**
**[measured]**. One burst of two hundred simultaneous hits leaves two hundred
components allocated for the rest of the match.

A second pool in the indicator system is fixed at ten entries with surplus
requests simply hidden **[measured]** — which is a legitimate policy, stated
nowhere.

**[derived]** The contrast between the two is the lesson: one pool has no
high-water policy and the other has an undocumented one. Both are the same
omission — **a pool is not correct until its exhaustion and trim behaviour are
written down.** Neither project reader can answer "what happens at peak?" without
reading the implementation.

Related and cheaper to fix: the live queue removes from the front of an array,
shifting the tail on every timer tick **[measured]**, where a ring buffer would
not move anything.

---

## 4. An identifier that is a count

The clearest single defect in the audit, and a good example of why protocol
identifiers deserve their own review rule.

A hit-marker batch is identified by **the current number of unconfirmed batches**
rather than by a monotonically increasing sequence **[measured]**.

**[derived]** The failure needs no packet loss to reason about. Batch A takes
identifier 0. Batch B takes 1. A is confirmed and removed. C now takes 1 — the
same identifier B is still holding. The confirmation handler matches on the first
entry with that identifier, so a confirmation for one batch can be applied to
another.

Compounding it, the same value is carried at **three different widths** along one
path: signed 32-bit at the source, unsigned 16-bit in the network call, and
unsigned 8-bit in storage **[measured]** — the last two declared sixteen lines
apart in the same header. Past 255 unconfirmed entries the storage wraps and the
network value does not, so matching stops entirely and the pending list grows
without bound.

Recipe: RC-09. The rules that fall out: identifiers are sequences, one width for
the whole path, and pending lists get a timeout and a drain policy.

---

## 5. Allocation in paint and arrange paths

Three instances, all in per-frame Slate code **[measured]**:

- a local array built and sorted on every arrange, without reserving;
- a full array copy returned by value from a getter called during paint;
- a **static** array used as scratch space in a draw helper.

**[derived]** The third is the interesting one, because it is an optimisation. It
avoids per-call allocation and introduces two new problems: the buffer is shared
by every instance of the widget in every window, and it is not thread-safe in a
context where paint is not guaranteed to be on one thread. The correct form —
a mutable member reset per call — is the same cost and none of the risk.

Recipe: RC-07. Also visible in the same code: a component lookup by class
performed both in paint and in tick, twice per frame, uncached **[measured]**.

---

## 6. Rebuild instead of diff

An interaction system destroys every descriptor object and creates new ones on a
tenth-of-a-second timer, for the same targets **[measured]**. Each cycle
allocates objects, invalidates observers, and drives a full add/remove cycle
through the indicator canvas.

**[derived]** The change-detection that gates this is itself unreliable: the
comparison sorts the candidate list only when the two lists have equal length
**[measured]**, so an equal-length reordering reports a change that did not
happen. In a crowd of interactable objects the rebuild runs ten times a second.

The fix is the general one: compute the desired set, diff against the current
set, and add and remove the difference. Recipe: RC-05.

A related ordering defect sits in the same subsystem: the add notification is
broadcast **before** the element is inserted **[measured]**, so a listener that
enumerates existing elements during that window either misses it or receives it
twice — and the receiving side adds without a duplicate check. Recipe: RC-10.

---

## 7. Statistics that are wrong before the window fills

The sample cache is pre-filled with zeroes at construction **[measured]**. Until
the ring wraps — which takes as many frames as its capacity — the minimum reads
zero and the average is divided by the full capacity rather than by the number of
real samples **[measured]**.

**[derived]** So the first seconds of every session report a minimum of zero and
an artificially low average, on a performance overlay whose entire purpose is to
be read during those seconds.

There is a second, quieter trap in the same class: a method named for the current
sample returns the **oldest** one, because the index points at the next write
position **[measured]**. The correctly-named sibling exists and is what the
project uses, which is why nobody noticed. Recipe: RC-08.

The cache itself is well bounded — capacity times sample size times statistic
count is on the order of tens of kilobytes **[derived]** — so this is a
correctness finding, not a memory one. Both matter; conflating them is how
"performance work" produces no performance.

---

## 8. Replication: name the axis

The audit's replication half produced no new defects and one clarification worth
carrying, because it is routinely got backwards:

| Mechanism | Memory | CPU | Bandwidth |
|---|---|---|---|
| Excluding presentation on a dedicated server | down | down | **unchanged** |
| Delta-serialised arrays | **up** (per-item key, per-connection state) | **up** (delta walk) | down |
| Subobject replication | down | down | down |
| Dormancy, relevancy, replication graph | — | down | down |

**[derived]** Two of these surprise people. Excluding cosmetics on a server saves
memory and CPU and changes bandwidth by exactly zero, because the intent still
replicates. And delta serialisation is a **bandwidth** optimisation that costs
memory and CPU — adopting it to "reduce replication cost" without naming the axis
can make the measured problem worse.

The genuine object-count reducer is subobject replication: many owned items, zero
additional actors and channels.

Before claiming any replication optimisation: state which axis improves and which
regresses, measure that axis specifically, and **confirm the mechanism is
actually enabled** — see `ue-multiplayer-authority`, NA-15, for a replication
graph that ships disabled with configured routing.

---

## 9. What to do with this list

In order of ratio of certainty to effort:

1. **Run once under an allocator that poisons freed memory**, with a mixed-style
   damage burst and with a latency module toggled on while the performance
   overlay is open. Those two scenarios turn RC-01 and RC-02 from arguments into
   crashes at the right line. **[open]** — this is the one experiment that
   settles the two critical findings.
2. **Add five counters to the existing profiling category** — pool size, live
   entries, pending protocol entries, active effect components, indicator count.
   The category and an example already exist in the audited project
   **[measured]**; extending it is three lines each and produces boundedness
   curves over a match, which is what actually distinguishes a cache from a leak.
3. **Grep for the two structural patterns** — stored container pointers, and
   `Empty()` in hot paths. Both are one command and both found real instances
   here.
4. Everything else is ordinary optimisation and can wait for a profile.

**[derived]** Note the shape of that list: the cheapest actions are the ones that
convert reading into evidence. A structural audit without step 1 produces a
plausible argument; with it, a defect report.

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6, read as source in
a single workspace: feedback and effect components, the indicator system, the
performance statistics subsystem, weapon state and targeting, equipment and
inventory, and the replication surface of each. Source addresses stay in the
research archive that produced this skill; each `RC-` identifier resolves back to
the audited location there.

## Evidence boundary

No profiler was run and no allocator instrumentation was used. Every finding is
structural, derived from reading; the growth characterisations are arguments
about code shape, not measurements. Quantities such as pool capacities and buffer
sizes are declared values read from source. Re-run the recipes and the two
scenarios above against your own tree before acting on any of it.
