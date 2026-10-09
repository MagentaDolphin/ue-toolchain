# Failure modes: gameplay messaging

Seventeen ways a tag-addressed message bus stops delivering, over-delivers, or
delivers into a void, without reporting anything useful.

The shared property of this list: **a bus converts a compile-time dependency into
a runtime one, and then does not check it.** The publisher compiles whether or not
anyone listens; the listener compiles whether or not anyone publishes. Every
entry below is a consequence of that trade, and the observable is almost always
the same — nothing happens, or something happens twice.

Recipes use `rg`. Two conventions worth stating once, because both cost real time
during the audit that produced this file:

- **Restrict searches to source globs.** An unrestricted search of a built tree
  matches compiled debug symbols, which are not code. In the measured reference a
  search for a suspected dead field returned four hits; three were `.pdb` files
  and the source truth was one. A count that includes build output is not a count
  of your code.
- **Most recipes are a pair of searches.** The defect class here is "the thing is
  present and the thing that would give it meaning is absent", and one search can
  only show the first half.

---

## Delivery correctness

### MB-01 - Listener removed using the wrong channel key

**Mechanism.** A hierarchical broadcast walks from the sent channel up through its
parents. Inside that walk, code that removes a listener addresses the removal by
the *original broadcast channel* rather than the ancestor tag currently being
visited. Handle IDs are allocated per channel, so the pair (channel, ID) is the
only unique identity.

**Why it is silent.** On the first iteration of the walk the two variables hold
the same value, so exact-match listeners — which is nearly all of them in most
projects — are removed correctly. The bug requires a listener registered on a
parent with partial matching *and* an expired payload type, simultaneously. Both
conditions are rare, and neither is an error on its own.

**Why the obvious check misses it.** The line reads correctly in isolation:
removing by "channel" is obviously right, and the variable is named `Channel`.
The defect is that the enclosing loop rebinds the meaning of "the channel we are
talking about" on every iteration, and the correct variable is three lines up in
the `for` header. Worse, the error-log line a few lines below uses the loop
variable correctly — so the file contains both the right and the wrong idiom, and
the wrong one is the one that mutates state.

**Symptom.** Two outcomes, both bad and neither loud. Either the stale listener is
never removed and a warning is emitted on every subsequent broadcast forever, or —
worse — an unrelated listener that happens to hold the same channel-local ID in
the broadcast channel's bucket is removed instead, and its owner silently stops
receiving messages.

**Detect.** Compare the loop variable against the key used for removal:

```bash
rg -n -A12 "for\s*\(.*RequestDirectParent" --glob "*.cpp" . \
  | rg "UnregisterListenerInternal|Remove\("
```

Read the output next to the `for` header. If the removal uses the loop's starting
value rather than the loop variable, that is this defect. In the measured
reference the walk iterated over an ancestor tag while removal passed the
broadcast channel.

**Guardrail.** When handle IDs are channel-local, make the removal API take the
pair and nothing else, and assert inside it that the pair was found. A removal
that silently finds nothing is how this defect stays invisible.

---

### MB-02 - Covariance in C++, equality in Blueprint

**Mechanism.** The C++ delivery path accepts a payload whose struct derives from
the listener's expected struct. The Blueprint async listener compares types with
strict equality.

**Why it is silent.** Both behaviours are individually reasonable and both are
implemented correctly. A Blueprint listener that does not match simply does not
fire, and not firing is the normal state of a listener most of the time.

**Why the obvious check misses it.** The two implementations live in different
files, written for different consumers, and each is correct against its own local
reasoning. There is no shared test matrix, because the two APIs are usually tested
by different people — the C++ one by whoever wrote the bus, the Blueprint one by
whoever first used the node. Nothing in either file mentions the other.

**Symptom.** A Blueprint listener subscribed to a base struct never fires for
derived payloads, while a C++ listener on the same base receives them. The
designer reports "the node never fires", which everyone investigates as a wrong
tag — the one hypothesis that is cheap to test and wrong.

**Detect.** Find both type gates and compare the operators:

```bash
rg -n "IsChildOf" --glob "*.cpp" .            # covariant gate
rg -n "StructType\s*==|== \w*StructType" --glob "*.cpp" .   # equality gate
```

Two different operators guarding the same conceptual check, in the same plugin,
is the finding. In the measured reference the C++ path used covariance and the
async Blueprint path used equality, on the same registration.

**Guardrail.** Pick one contract, write it down, and run one test matrix through
both APIs. If they must differ, the difference belongs in the node's tooltip, not
only in the source.

---

### MB-03 - Type check disabled by an empty type pin

**Mechanism.** Registering with a null expected struct type sets a flag that
disables the type check entirely, so the listener receives any payload. The path
is documented as internal — and is reachable from a Blueprint node whose payload
type pin was left empty.

**Why it is silent.** Nothing fails. The listener receives messages, possibly
several unrelated kinds, and the Blueprint graph downstream either uses the
payload or does not. There is no log, because from the bus's point of view the
listener asked for exactly this.

**Why the obvious check misses it.** The comment on the branch says "for internal
use", and reviewers believe comments about intent. Confirming reachability means
tracing a Blueprint pin's default value into a factory function into a private
registration call — three hops across two modules, none of which look
interesting.

**Symptom.** In Blueprint, usually nothing worse than a payload extraction that
returns false. In C++, the same path combined with a templated callback would
reinterpret unrelated bytes as the expected struct, which is undefined behaviour
with no diagnostic.

**Detect.** Find the escape hatch and then find who can reach it:

```bash
rg -n "bHadValidType|StructType\s*==\s*nullptr" --glob "*.cpp" --glob "*.h" .
rg -n -B4 "RegisterListenerInternal\(" --glob "*.cpp" . | rg -i "Get\(\)|nullptr"
```

Any caller that can pass a null type is a caller that can disable the check.

**Guardrail.** If a code path must exist for internal reasons, make it
inaccessible rather than merely undocumented — a private overload, a passkey
type, or a compile-time gate. Reject an unresolved wildcard payload at Blueprint
compile time.

---

### MB-04 - Payload pointer retained after the callback returns

**Mechanism.** The bus passes a pointer to the sender's stack object rather than
copying. A listener stores that pointer.

**Why it is silent.** The memory is still mapped and, for a short while, still
holds the right bytes. Reading it immediately after the broadcast usually works.
The failure requires the stack to be reused, which depends on what runs next.

**Why the obvious check misses it.** The callback signature hands you a reference,
and references are normally safe to keep. Nothing in the type expresses "valid
until this function returns". The one place the constraint is written down is the
bus's own documentation, which the person writing the listener has no reason to
open.

**Symptom.** Corrupted payload fields read at a later tick — values that are
plausible, occasionally correct, and change with unrelated code. This is one of
the few entries in this file that produces a crash, and the crash is far from the
cause.

**Detect.** Find listeners that store rather than consume:

```bash
rg -n -A8 "void .*\(FGameplayTag\s+\w+,\s*const\s+F\w+&\s*\w+\)" --glob "*.cpp" . \
  | rg "=\s*&|Ptr\s*=|AddRaw|CopyRef"
```

Any assignment of the payload's address into a member is the finding. A copy of
the payload by value is fine.

**Guardrail.** State the lifetime in the callback's own documentation, and copy at
the boundary. Where the bus crosses into a scripting layer, copy by value — the
measured reference does exactly this for its Blueprint path, and nulls the stored
pointer immediately after the delegate returns.

---

## Ownership and lifetime

### MB-05 - The convenient overload cannot express the match type

**Mechanism.** Three registration overloads exist. The one that binds a UObject
member weakly — the safest and by far the most used — delegates to the raw form
without forwarding the match type, so it is always exact.

**Why it is silent.** Exact matching is the right default, so every listener
registered this way behaves correctly. The feature that is unavailable is one
nobody is currently trying to use, and its absence produces no error because you
cannot pass the argument at all.

**Why the obvious check misses it.** The feature is fully implemented, documented
in the enum, exposed in the Blueprint node, and covered by the broadcast walk. A
review that asks "do we support hierarchical matching?" finds all of that and
answers yes. The gap is one unforwarded default argument in a header.

**Symptom.** A project ships a complete hierarchical matching implementation that
nothing in its own C++ ever uses, and nobody notices, because using it requires
switching to a less convenient overload for reasons that are never stated.

**Detect.** Count the feature's declaration sites against its use sites, and
exclude the implementation itself:

```bash
rg -n "PartialMatch" --glob "*.h" --glob "*.cpp" .            # declared
rg -n "PartialMatch" --glob "*.cpp" . | rg -v "MessageRouter|MessageSubsystem"
```

An empty second result with a rich first result is the finding. In the measured
reference the game code used partial matching zero times; the only similarly
named symbols elsewhere belonged to two unrelated subsystems that had copied the
pattern.

**Guardrail.** Every overload of a registration API forwards every option, or the
option does not exist. If an overload deliberately restricts, name it so —
`RegisterExactListener` — rather than silently dropping an argument.

---

### MB-06 - Parameter struct with no bound callback returns an invalid handle silently

**Mechanism.** The options-struct registration form checks that a callback is
bound and, if not, returns a default-constructed invalid handle without
registering and without logging.

**Why it is silent.** The caller receives a handle-shaped value. Storing it,
passing it around and eventually unregistering it all work. The only difference
is that nothing was ever registered.

**Why the obvious check misses it.** The return type is not optional and not an
error code; it is a handle, and handles look like success. Checking validity
requires knowing that this overload can fail, which is stated nowhere at the call
site.

**Symptom.** A listener that never receives anything, in code that reads as fully
wired. Because unregistration of an invalid handle is also silent, no part of the
lifecycle complains.

**Detect.** Find registrations whose returned handle is never validity-checked:

```bash
rg -n "RegisterListener\(" --glob "*.cpp" . -A3 | rg -v "IsValid|ensure|check"
```

**Guardrail.** Return an explicit failure, or log at warning level, or assert in
development builds. A silent failure path on a registration API is a listener
that cannot be debugged.

---

### MB-07 - Async listener outlives its owner until the next message

**Mechanism.** An async listen action detects its owner's death by noticing that
its dynamic delegate is no longer bound — which it can only do *while handling a
message*. Until the next message arrives, the action and its registration stay
alive.

**Why it is silent.** The cleanup does eventually happen, and it happens before
anything observable goes wrong. On a busy channel the window is a frame.

**Why the obvious check misses it.** There *is* cleanup, and reading it shows
correct logic. The gap is a timing property — cleanup is driven by traffic rather
than by the owner's destruction — and timing properties are invisible in a code
review that asks "is cleanup implemented?".

**Symptom.** On a quiet channel, listener records accumulate for destroyed
owners. On a shutdown path, the last message of a session may be delivered into
an object graph that is already tearing down.

**Detect.** Find cleanup that is triggered by message handling rather than by
destruction:

```bash
rg -n -B6 "SetReadyToDestroy" --glob "*.cpp" . | rg -i "IsBound|HandleMessage"
rg -n -i "//\s*@?TODO.*(proactive|cleanup)" --glob "*.cpp" .
```

The second command matters: in the measured reference the authors had recorded
exactly this limitation as a TODO with a tracker reference, which is the
strongest possible confirmation that a finding is real and known.

**Guardrail.** Tie the async action's lifetime to its owner's destruction
directly, not to the arrival of the next message.

---

### MB-08 - Listener map is not cleared on map travel

**Mechanism.** A GameInstance-scoped bus is cleared only at GameInstance
teardown. Listeners registered by objects belonging to a world that has been
travelled away from remain in the map.

**Why it is silent.** Weak binding means the dead objects are never called. The
records are inert: they cost memory and a little iteration time, and produce no
wrong behaviour.

**Why the obvious check misses it.** Deinitialisation exists and is correct for
the scope it was written for. "Does the bus clean up?" is answered yes. The
question that finds this is narrower — *at which lifecycle event?* — and the
answer is one that only matters in a project that travels between maps, which a
single-map test never does.

**Symptom.** Listener counts that grow monotonically across a session of map
changes. Diagnosis is difficult because the leak is bounded by session length and
the objects themselves are correctly garbage collected.

**Detect.** Find the scope and the reset point, and compare them:

```bash
rg -n "public UGameInstanceSubsystem|public UWorldSubsystem" --glob "*.h" .
rg -n -A4 "::Deinitialize\(\)" --glob "*.cpp" . | rg "Reset\(|Empty\(|Clear\("
```

A GameInstance scope whose only reset is in `Deinitialize` leaks across travel by
construction. Confirm at runtime: log the listener count, travel, log again.

**Guardrail.** Either scope the bus to the world, or hook map change and drop
records whose weak owner has expired. A weak callback is not an unsubscription.

---

### MB-09 - Teardown calls an accessor that asserts

**Mechanism.** The static accessor resolves the world with an assert-on-failure
mode and then asserts on both the world and the subsystem. Teardown code calls it
to unregister.

**Why it is silent.** In every ordinary shutdown the world is still present when
components tear down, so the asserts pass. The failure needs an unusual teardown
order — a subsystem destroyed first, PIE cancelled mid-initialisation, a level
unloaded during travel.

**Why the obvious check misses it.** Unregistering in `EndPlay` is the correct
pattern and is what a reviewer is looking for. That the *accessor* is the
strictest of the several available ways to reach the subsystem is a property of a
different file.

**Symptom.** An assert during shutdown, in a build configuration and teardown
order that nobody can reproduce on demand, at a call site that is doing the right
thing.

**Detect.** Find teardown paths that use the asserting accessor:

```bash
rg -n -B2 -A2 "::EndPlay|NativeDestruct|BeginDestroy" --glob "*.cpp" . \
  | rg "Subsystem::Get\(|::Get\(this\)"
rg -n -A6 "static .*& Get\(" --glob "*.h" . | rg "Assert|check\("
```

The pairing is the finding: an asserting accessor called from a destruction path.
In the measured reference this pattern appeared in three separate consumer
classes, all of which could have unregistered through the handle instead.

**Guardrail.** Unregister through the handle, which resolves the subsystem weakly
and no-ops when it is gone. Provide a non-asserting accessor and use it in every
teardown path.

---

## Contract and vocabulary

### MB-10 - The channel string is the contract, declared in several places

**Mechanism.** Publisher and each subscriber declare their own file-local tag
constant for the same channel string. The engine deduplicates by string, so it
works.

**Why it is silent.** It is correct. Every site resolves to the same tag, the join
succeeds, and the arrangement has a real benefit: modules do not depend on each
other's headers.

**Why the obvious check misses it.** Each declaration is locally idiomatic and
each file reads well. Nothing links them. A rename in one file compiles, links,
and passes review — and the reviewer of that file has no way to see the other
three.

**Symptom.** Editing one declaration silently detaches one participant from the
channel. This is the symmetric-typo failure from tag governance, arriving through
a different door: correctness means all sites agree, not that any one is right.

**Detect.** Count independent declarations per channel string:

```bash
rg -o -N 'UE_DEFINE_GAMEPLAY_TAG[_A-Z]*\([^,]+,\s*"([^"]+)"' -r '$1' \
  --glob "*.cpp" . | sort | uniq -c | sort -rn | head
```

Any string with a count above one is a contract with several owners. In the
measured reference one elimination channel was declared independently at four
sites — the publisher and three separate processors in a feature plugin.

**Guardrail.** Shared channels live in one header owned by the publisher. Keep
file-local declarations only for channels that never leave their file.

---

### MB-11 - Listener order assumed without a contract

**Mechanism.** Nothing guarantees callback order, and removal by swap-with-last
actively reorders the array as a side effect of unrelated unsubscriptions.

**Why it is silent.** An order exists on every run and is stable as long as
nothing unsubscribes. Code that depends on it works, and keeps working, until an
unrelated feature adds a listener or removes one.

**Why the obvious check misses it.** The dependency is never written down —
that is what makes it an assumption. No search finds "this listener must run
first"; the knowledge lives in the fact that it currently does.

**Symptom.** Ordering-dependent behaviour that changes when an unrelated system
subscribes, in a different module, in a different release.

**Detect.** Find the removal strategy and the documented guarantee, and check for
listeners that mutate shared state:

```bash
rg -n "RemoveAtSwap|RemoveSwap" --glob "*.cpp" .
rg -n -i "order.*not guaranteed|call order" --glob "*.h" .
```

If the second command finds an explicit warning from the bus authors, the
guarantee does not exist and any dependence on order is yours to remove.

**Guardrail.** If ordering matters, it is not a bus concern — sequence the work in
one owner and broadcast the outcome. Never introduce priority through
registration order.

---

### MB-12 - Reentrancy with no depth limit

**Mechanism.** Broadcasting from inside a listener callback is legal and
supported. Nothing bounds the recursion.

**Why it is silent.** It is a legitimate and useful pattern — an aggregator that
consumes one channel and publishes a derived fact on another does exactly this.
The dangerous case differs only in that the graph of channels contains a cycle.

**Why the obvious check misses it.** Each listener is individually correct and
each broadcast is individually justified. The cycle exists in the graph formed by
several modules, which no file shows, and which a feature plugin can complete by
adding one processor.

**Symptom.** Stack overflow, or a hang, with a call stack that is one repeating
pattern thousands of frames deep and no obvious origin.

**Detect.** Map the graph: which listeners publish, and on which channels?

```bash
rg -n -B10 "BroadcastMessage\(" --glob "*.cpp" . \
  | rg -B2 "OnMessageReceived|::Handle\w*Message"
```

Every hit is an edge from an input channel to an output channel. Draw them and
look for a cycle. In the measured reference this pattern was present and
deliberate — a processor consuming eliminations and publishing assists — with no
cycle, which is the correct state and worth confirming rather than assuming.

**Guardrail.** Keep a broadcast-depth counter in development builds and assert
past a small bound. Document, per processor, which channels it reads and writes.

---

## Scope and misuse

### MB-13 - A message used where state is required

**Mechanism.** A fact is published as an event only. A listener that subscribes
after the event has no way to learn it.

**Why it is silent.** Every listener that existed at publication time is correct.
Subscription usually happens during initialisation, before anything interesting
has been published, so the whole system is correct for the entire development
period.

**Why the obvious check misses it.** Testing subscribes early by construction —
you start the game, the widget is created, then things happen. Reproducing
requires a listener created *after* the fact, which means mid-match widget
creation, a late-joining client, or a feature activated at runtime.

**Symptom.** A widget created mid-match shows a default value forever. A late
joiner's UI is empty while everyone else's is correct.

**Detect.** For each channel, ask whether any subscriber can be created late:

```bash
rg -n "RegisterListener\(" --glob "*.cpp" . -B6 | rg -i "NativeConstruct|BeginPlay|OnActivated"
```

Widget construction and feature activation are the late-creation paths. For each,
apply the test from the skill: if a listener subscribing one second late must know
the current value, the fact is state and the bus is the wrong carrier.

**Guardrail.** Replicate or store the state; use the message purely as a change
notification. On subscription, read the current value directly from its owner —
which requires that the value have an owner, and that is the real design output.

---

### MB-14 - A command disguised as an event

**Mechanism.** A message is published to make something happen, rather than to
report that it has happened.

**Why it is silent.** With exactly one listener it behaves identically to a
function call. It works, and it looks decoupled.

**Why the obvious check misses it.** The mechanism is indistinguishable from
correct use — same API, same payload shape. Only the *name* reveals it, and names
in the imperative mood ("give", "apply", "spawn") pass review because they
describe what the sender wants.

**Symptom.** Zero listeners means the command is silently dropped with no failure
result. Two listeners means it happens twice. Neither is reported, because a bus
has no concept of a required handler.

**Detect.** Grep the channel vocabulary for the imperative mood:

```bash
rg -o -N '"([A-Za-z]+\.[A-Za-z.]*Message[A-Za-z.]*)"' -r '$1' --glob "*.cpp" . \
  | sort -u | rg -i "^\w+\.(Add|Give|Set|Apply|Spawn|Request|Please|Do)"
```

A channel named for an action rather than for a completed fact is the finding.
Past-tense names — "equipped", "eliminated", "changed" — are the correct shape.

**Guardrail.** Commands go to one accountable handler that can fail and say so.
Events report facts in the past tense and tolerate zero listeners.

---

### MB-15 - Broadcast treated as replication

**Mechanism.** A message is published on the server and expected to reach
clients. The bus is local to one process and has no networking at all.

**Why it is silent.** In a single-process test — the editor's default multiplayer
mode — the host and its client share one process and, depending on the bus's
scope, may share one instance. The message appears to cross the network.

**Why the obvious check misses it.** Everything about the code reads as
transport: a channel, a payload, publish and subscribe. The absence of networking
is a property of a module's dependency list, which is not where anyone looks when
reasoning about a message flow.

**Symptom.** A feature that works in the editor and does nothing on a dedicated
server. Alternatively, a listen server processes both the server-side publication
and the client-side rebroadcast and everything happens twice.

**Detect.** Prove the absence, then find who assumed otherwise:

```bash
rg -n "UFUNCTION\([^)]*(Server|Client|NetMulticast)|NetSerialize|Replicated" \
  --glob "*.cpp" --glob "*.h" <bus-module-path>/     # expect: nothing
rg -n -B4 "BroadcastMessage\(" --glob "*.cpp" . | rg "HasAuthority|WITH_SERVER_CODE|NM_"
```

The second command finds the correct pattern as well as the incorrect one: a
net-mode check before a rebroadcast is the guard that prevents double processing
on a listen server. Its absence next to a rebroadcast is the finding.

**Guardrail.** Replicate state or send an RPC; rebroadcast locally on arrival;
guard the rebroadcast with a net-mode check so a listen server does not process
both paths.

---

## Cost

### MB-16 - Per-broadcast copy of the listener array

**Mechanism.** For mutation safety the listener array of each non-empty bucket is
copied before iteration. The copied element type holds a callable object, whose
copy may allocate.

**Why it is silent.** It is correct, and correctness was the reason for it. The
cost is proportional to broadcast frequency times listener count times tag depth,
and all three are small early in a project.

**Why the obvious check misses it.** The line is a defensive copy with a comment
explaining why it is needed, which is exactly what a reviewer wants to see. The
cost is invisible unless you know that the element type is expensive to copy —
which requires reading a different struct in a different header.

**Symptom.** Allocator churn proportional to message traffic, appearing in
profiles as generic allocation cost rather than as bus cost. Discovered when a
high-frequency channel — damage in a shooter — is added late.

**Detect.** Find the copy and the depth walk, then measure:

```bash
rg -n -B2 "TArray<\w*ListenerData>\s*\w+\(" --glob "*.cpp" .
rg -n "RequestDirectParent" --glob "*.cpp" .
```

Both present means cost per broadcast scales with tag depth even when no
hierarchical listener exists. Confirm with an allocation profile while
broadcasting on the highest-frequency channel.

**Guardrail.** Copy handles rather than callables, or iterate an index with a
generation counter, or skip the ancestor walk when the bucket count for parent
tags is zero. Measure before optimising — this is a real cost, not a large one.

---

### MB-17 - A declared field nobody uses, and the search that hides it

**Mechanism.** A member is declared in a public struct, never written and never
read. It survives because removing it feels risky.

**Why it is silent.** An unused field costs a few bytes and nothing else. It
serialises, copies and compiles like any other member.

**Why the obvious check misses it.** This entry is here less for the dead field
than for the search that fails to prove it dead. A naive recursive search of a
built project matches compiled debug symbols, so a field with exactly one source
occurrence returns several hits and reads as "in use". The instrument reports the
build output as if it were code.

**Symptom.** Dead API surface that persists across refactors, plus — more
expensively — a general loss of trust in the searches used to make deletion
decisions.

**Detect.** Search source only, and say so explicitly:

```bash
F='StateClearedHandle'
rg -n "\b$F\b" --glob "*.h" --glob "*.cpp" .        # source truth
rg -n "\b$F\b" .                                    # unfiltered, for contrast
```

In the measured reference the filtered search returned exactly one line — the
declaration — while the unfiltered one returned four, three of them debug-symbol
files. Always compare the two before concluding either "dead" or "in use".

**Guardrail.** Restrict every deletion-decision search by file type. Delete dead
fields in the same change that proves them dead, and record the search you ran.
