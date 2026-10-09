# Failure modes: runtime allocation and caching

Ten ways a running game allocates more each minute, keeps what it should drop, or
dereferences memory that moved.

The shared property splits this list in two, and the split is worth stating
because it changes how you look for each half.

**The dangling-pointer half is data-dependent.** It needs a second key inserted
while a first entry is still live, or a new statistic to appear mid-session.
Neither happens in a short test, both happen in a match, and the crash lands far
from the cause. A null check never catches it, because the pointer is not null.

**The growth half is time-dependent.** Nothing is wrong at any instant; the
defect is a slope. A single memory sample cannot show it and a single frame
cannot contain it, which is why every recipe below asks for two measurements
rather than one.

Recipes use `rg` from a project source root, and were executed against the
audited project while this file was written.

---

## Pointers into moving storage

### RC-01 - A raw pointer into a map value, held across frames

**Mechanism.** A reference to a map value is taken, its address is stored in a
long-lived entry, and the map later gains a key. The map reallocates; the stored
address points into freed memory.

**Why it is silent.** Until a second key arrives, the address stays valid and
everything works. The window is narrow and specific — a live entry plus an insert
— so ordinary play produces it and ordinary testing does not.

**Why the obvious check misses it.** The code often *has* a check, and the check
passes: the pointer is not null, it is non-null garbage. Reading the storing line
shows a reference to a pool, which is exactly what the entry needs. The defect is
a property of the container's reallocation behaviour, which is nowhere in view.

**Symptom.** A crash inside the pooled object's own method, under load, with a
stack that looks like the pool is corrupt. In the audited project the window is a
one-second component lifespan plus a second visual style — trivially produced by
mixed normal and critical damage in the same second.

**Detect.** Find addresses taken from containers and stored:

```bash
rg -n -B2 -A4 "FindOrAdd\(|\.Find\(" --glob "*.cpp" . | rg "&\w+|Emplace\(|= &"
rg -n "\w+\*\s+\w+ = nullptr;" --glob "*.h" . | rg -i "pool|cache|list|entry"
```

The second search finds the *declaration* side — a bare pointer member whose name
suggests it points at a collection — which is often easier to spot than the
assignment.

**Guardrail.** Store a key or an index and resolve at use. If a stable address is
genuinely required, use a container that guarantees stable element addresses and
say so at the declaration. When you suspect one, run under the allocator's stomp
mode: it converts a probabilistic corruption into a deterministic crash on the
right line, and costs one run.

---

### RC-02 - A cache pointer handed out and stored by a widget

**Mechanism.** A subsystem returns a pointer into its own map so a widget can
read samples cheaply. The widget stores it. The map grows a key when a new data
source appears — a network connection, an optional module — and reallocates.

**Why it is silent.** The optimization is real and the pointer is valid at hand-
out. Growth is lazy and event-driven: the map gains keys minutes into a session,
when a connection is established or a feature is enabled, long after the widget
cached its pointer.

**Why the obvious check misses it.** Both sides are idiomatic. Returning a
pointer to avoid copying a sample buffer is good practice; caching it to avoid a
lookup per frame is also good practice. Neither side knows the map is still
growing, and nothing in either signature says the pointer has a lifetime.

**Symptom.** A crash in the widget's paint path, appearing only after the session
has been running long enough to acquire a new statistic — and therefore never in
a short repro. Compounded when the subsystem's teardown resets the tracker while
the widget still holds the pointer.

**Detect.** Find getters returning interior pointers, then find who stores them:

```bash
rg -n "const \w+\* \w+::Get\w*Data\(" --glob "*.cpp" . -A4 | rg "\.Find\("
rg -n "const \w+\* \w+ = nullptr;" --glob "*.h" . | rg -i "widget|graph|view"
```

A getter returning `Find` on a member map, plus a member pointer of that type in
a widget, is the pair.

**Guardrail.** Return a copy of the small value, or a handle the subsystem can
invalidate, or require the caller to re-fetch each frame. If a pointer must
escape, give the subsystem an invalidation broadcast and make subscribing
mandatory.

---

## Unbounded growth

### RC-03 - Read, append, write back — with no clear

**Mechanism.** Each event fetches an entire collection from another system,
appends one element, and writes the whole thing back. Nothing ever clears it.

**Why it is silent.** Every individual call is correct and fast. The array is a
legitimate data channel to the effects system, and its contents are consumed
visually, so nobody looks for a removal path.

**Why the obvious check misses it.** The two lines read as an idiomatic
accessor pair. The cost — two full copies per event — is invisible at small sizes,
and the growth is invisible without a second measurement. Reviewing the function
shows three lines of correct code.

**Symptom.** Cost per event rising through a match, total work quadratic in event
count, and memory that never returns. In a damage-number path this means the
hundredth hit costs measurably more than the first.

**Detect.** Find get-append-set triples on the same key:

```bash
rg -n -A3 "= \w*::Get\w*Array\w*\(" --glob "*.cpp" . | rg "Add\(|SetNiagara|Set\w*Array"
```

Then, for each hit, search the file for any clear:

```bash
rg -n "Empty\(\)|Reset\(\)|SetNum\(0\)|Clear" <that-file>
```

An append path with no clear anywhere in the file is the finding.

**Guardrail.** Give the collection an owner and an eviction rule — a cap, a
time-out, or a clear on the event that logically ends its contents. If the
consuming system owns the lifetime, ask it for a removal API rather than
assuming one.

---

### RC-04 - Re-append every previous element on every trigger

**Mechanism.** A component that spawns audio and effect components copies all
previously active ones into temporary arrays, appends the new ones, and writes
the union back — with no removal of finished components.

**Why it is silent.** Effects play and stop correctly, because stopping is the
component's own business. What accumulates is the *references*, and those are
invisible until something counts them.

**Why the obvious check misses it.** The function reads as careful state
management: gather, combine, store. The absent operation is a filter for finished
components, and absence in a function that is otherwise thorough is the hardest
kind to see.

**Symptom.** Thousands of retained effect components after a match. Because the
arrays are strong references, none of them can be collected, so this is
simultaneously a memory leak and a quadratic allocation profile in the hottest
cosmetic path — footsteps, at a few per second.

**Detect.** Find union-rebuild patterns and check for a prune:

```bash
rg -n -B4 -A6 "\.Append\(" --glob "*.cpp" . | rg "Empty\(\)|Reset\(\)"
rg -n "UPROPERTY\(Transient\)" -A2 --glob "*.h" . | rg "TArray<TObjectPtr<U\w*(Audio|Niagara|Particle)"
```

The second search alone is worth running in any project: a strong transient array
of effect components is a retention decision, and it needs a removal path.

**Guardrail.** Filter finished components on each pass, or use weak references
and let the components own their own lifetime. Prefer the reset-without-freeing
operation to the one that releases the buffer — see RC-06.

---

### RC-05 - Rebuilding descriptors on a timer instead of diffing

**Mechanism.** A periodic scan removes all its descriptor objects and creates new
ones for the same targets, several times a second.

**Why it is silent.** The result is correct: the right descriptors exist
afterwards. Object creation is fast enough that no single frame stands out.

**Why the obvious check misses it.** The function reads as a clean rebuild —
clear, then populate — which is a legitimate and common shape. The cost is in the
frequency, which is set elsewhere as a scan rate, and in the downstream churn:
each create and destroy propagates through observers into widget pooling and
canvas slot management.

**Symptom.** Steady allocation and observer churn while the player stands still
in a crowd of interactive objects. Profiles show constant low-level cost with no
obvious owner.

**Detect.** Find object creation inside timer-driven update functions:

```bash
rg -n -B10 "NewObject<" --glob "*.cpp" . | rg "Update\w+\(|OnTimer|ScanRate"
rg -n "ScanRate|Interval|SetTimer" --glob "*.h" --glob "*.cpp" . | rg -i "0\.[0-9]"
```

Also check the change-detection that gates the rebuild: comparison logic that
sorts only when sizes match will report a change on any reorder, making the
"only when changed" guard ineffective.

**Guardrail.** Diff against a stable key and reuse descriptors. If a rebuild is
genuinely simpler, measure it at the worst-case target count before accepting the
scan rate.

---

### RC-06 - Freeing the buffer in a hot path

**Mechanism.** The container operation that releases memory is used where the one
that keeps capacity was intended, in code that runs many times per second.

**Why it is silent.** Both operations leave the container empty and both are
correct. The difference is whether the next fill reallocates.

**Why the obvious check misses it.** The two calls are one word apart and read
identically at a glance. Nothing distinguishes a hot path from a cold one in the
call itself, and in teardown code the freeing version is the right choice — so the
same line is correct in one file and wrong in another.

**Symptom.** Allocator churn proportional to event frequency, showing up as
generic allocation cost rather than attributable to the system causing it.

**Detect.** Find the freeing operation and classify each site by frequency:

```bash
rg -n "\.Empty\(\)" --glob "*.cpp" . -B6 | rg -i "tick|paint|onhit|effect|update"
```

Teardown sites are fine. Anything reached more than once a second is the finding.
In the audited project the two hottest cosmetic arrays are freed and refilled on
every footstep.

**Guardrail.** Reset in hot paths, free at teardown, and write the reason in a
comment when it is not obvious which one a site is.

---

### RC-07 - Allocating in a paint or arrange path

**Mechanism.** A per-frame layout or paint function builds a local array, without
reserving, and lets it reallocate as it fills.

**Why it is silent.** It is correct, local and easy to read. The cost is a
handful of small allocations per frame, which no single profile sample
attributes.

**Why the obvious check misses it.** A local array in a function is the most
ordinary thing in the file. Knowing it matters requires knowing the function is
called once or more per frame — which is a property of the caller.

**Symptom.** A frame-time floor that nothing accounts for, and allocator pressure
that scales with the number of on-screen elements.

**Detect.** Find containers declared in per-frame widget paths:

```bash
rg -n -A12 "::OnPaint\(|::OnArrangeChildren\(|::Tick\(" --glob "*.cpp" . \
  | rg "TArray<|TMap<"
rg -n "static TArray|static TMap" --glob "*.cpp" . | rg -i "widget|slate|paint"
```

The second search finds the wrong fix for the first: a static container avoids the
allocation and introduces sharing between every instance of the widget, plus a
thread-safety assumption nobody wrote down. In the audited project both appear —
one path allocates per frame, another uses a static.

**Guardrail.** A mutable member with a reset at the top of the function. Not a
local, not a static.

---

## Semantics

### RC-08 - A prefilled ring buffer reporting statistics

**Mechanism.** A fixed-capacity sample cache is filled with zeroes at
construction. Minimum, average and related statistics include the prefix until
the buffer wraps.

**Why it is silent.** Every value returned is a real number computed correctly
from the buffer's contents. There is no error state for "not enough samples yet",
because the buffer is always full.

**Why the obvious check misses it.** The implementation is correct for a full
buffer, and a reviewer checks the arithmetic rather than the initial condition.
The distortion disappears after a few seconds, so it is gone before anyone
investigates.

**Symptom.** A minimum of zero and a depressed average on any graph for the first
seconds after it appears — which is exactly when someone is looking at it.

**Detect.** Find prefilled buffers and check whether the statistics account for
fill level:

```bash
rg -n "AddZeroed\(|SetNumZeroed\(" --glob "*.h" --glob "*.cpp" .
rg -n -A6 "GetMin\(\)|GetAverage\(\)" --glob "*.h" . | rg "Num\(\)|SampleSize|NumValid"
```

Statistics dividing by capacity rather than by a fill count is the finding.

**Guardrail.** Track the number of valid samples and compute over that window.
Also check the accessor names: an index-based "current" that returns the *next
write position* is the oldest sample, not the newest — a naming trap worth
checking in any ring buffer.

---

### RC-09 - An identifier that is a count, at three different widths

**Mechanism.** A batch identifier is assigned from the number of in-flight
batches rather than a monotonic sequence, so identifiers are reused as batches
complete. Separately, the same value is one width at the source, another in the
message, and a third in storage.

**Why it is silent.** With one or two batches in flight, counts and sequences are
indistinguishable. The width mismatch is invisible until the value exceeds the
smallest type — which needs sustained fire and a degraded connection.

**Why the obvious check misses it.** Each half is defensible alone: a count is a
plausible identifier when everything completes promptly, and each width is
reasonable in its own context. Confirming means reading a declaration, a
constructor and a message signature that are not adjacent — in the audited project
the storage width and the message width are sixteen lines apart in the same
header, which is exactly far enough.

**Symptom.** Confirmations applied to the wrong batch when identifiers are
reused, and — once the counter passes the narrow type's range — confirmations that
match nothing at all, so the pending list grows without bound.

**Detect.** Trace one identifier through the whole path and compare widths:

```bash
I='UniqueId'
rg -n "\b$I\b" --glob "*.h" --glob "*.cpp" .
```

Read the output as a table of types. Then check the assignment: an identifier
taken from a `Num()` or a count getter is a reused identifier.

**Guardrail.** One monotonic sequence, one width, asserted at every boundary.
Define wrap behaviour. Give the pending list a timeout and a drain, so a matching
failure degrades instead of accumulating.

---

### RC-10 - Broadcasting before the state is consistent

**Mechanism.** A registry broadcasts an "added" event before inserting the item
into its own collection. A listener that responds by enumerating the collection
sees a state that does not include the item it was just told about.

**Why it is silent.** For a listener that only uses the event payload, the order
is irrelevant and everything works. The defect needs a listener that also reads
the collection — typically one doing late binding, catching up on existing items.

**Why the obvious check misses it.** Two adjacent lines, both correct, in an
order that reads naturally: announce, then record. Reversing them looks like a
stylistic preference until you know a listener enumerates.

**Symptom.** An item lost or added twice, depending on which listener ran when.
In the audited project a canvas both handles the event and enumerates existing
items on attach, and it adds to its own list without a duplicate check.

**Detect.** Find broadcasts that precede the mutation they announce:

```bash
rg -n -B2 -A2 "\.Broadcast\(" --glob "*.cpp" . | rg "Add\(|Remove\(|Emplace\("
```

A broadcast on the line *before* the insert is the finding. Then check the
listener for a duplicate guard.

**Guardrail.** Mutate, then broadcast. Listeners must observe a consistent
container, and any listener that also enumerates on attach needs an idempotent
add.
