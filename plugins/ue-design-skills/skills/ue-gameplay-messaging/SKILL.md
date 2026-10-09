---
name: ue-gameplay-messaging
description: >-
  Design, implement or review a typed tag-addressed pub/sub message bus in
  Unreal Engine: subsystem scope and lifetime, struct type checks, exact versus
  hierarchical channel matching, listener handles and ownership, parity between
  the C++ and Blueprint APIs, the local-versus-network boundary, and migration
  from direct dependencies. Use when decoupling gameplay from UI, feedback,
  telemetry or processors, or when debugging duplicate, stale, mismatched or
  wrongly replicated messages.
---

# UE gameplay messaging

The invariant:

> Messages announce facts inside one process. They do not own state, ordering,
> persistence, authority or replication.

Measured patterns from a reference product: [patterns](references/patterns.md).
Seventeen detection recipes for silent bus failures:
[failure modes](references/failure-modes.md).

Read the failure modes before adopting a bus implementation. Each entry names the
mechanism, why it stays silent, why the obvious check misses it, and a command you
can run against your own tree.

Related skills: `ue-gameplay-tag-governance`, `ue-ui-architecture`,
`ue-gas-architecture`, `ue-multiplayer-authority`, `ue-data-driven-architecture`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Choose the bus scope explicitly

A bus implemented as a GameInstance subsystem:

- is shared by every world belonging to that GameInstance;
- survives map travel;
- is destroyed at GameInstance teardown;
- is local to one process;
- does **not** replicate.

That scope suits:

- gameplay event → HUD and feedback;
- local processors and telemetry;
- decoupling feature plugins from the base module;
- cross-system notifications where no receiver owns the sender.

It is unsuitable as the source of truth for:

- inventory, team or score state;
- guaranteed ordered workflows;
- cross-process communication;
- persistence;
- anything an RPC should carry.

### The state-versus-event test

Ask: **"if a listener subscribes one second late, must it know the current
value?"**

- **yes** → replicated property or state component, plus a change notification;
- **no** → a transient message may be appropriate.

"An elimination occurred" is an event. "The current team score" is state. A bus
that is asked to answer the second question will appear to work for every
listener that happened to be subscribed early, which is every listener during
development.

---

## 2. Storage model and handle identity

```text
map: channel tag -> channel listener list

channel listener list
├─ monotonically increasing handle ID (local to THIS channel)
└─ listeners[]
   ├─ callback
   ├─ weak expected struct type
   ├─ had-valid-type flag
   ├─ handle ID
   └─ exact / partial match
```

Registration returns a handle carrying the subsystem, the channel, and the
channel-local ID. **The handle is the ownership receipt.** The caller, or an RAII
wrapper, retains it and unregisters when its lifecycle ends.

### The handle identity rule

If IDs are allocated per channel, then **every internal removal must use both the
registration channel and the ID.** Never search another channel by ID alone.

This is not a stylistic point. A hierarchical broadcast walks several channels in
one call; code written inside that walk has two plausible variables in scope — the
channel the message was sent on, and the channel currently being visited — and
they are the same value only on the first iteration. Recipe: MB-01.

---

## 3. Typed broadcast

Template the C++ API and resolve the struct type at compile time on both sides.
Store the expected type at registration.

On broadcast, the payload is deliverable when:

```text
broadcast struct IsChildOf listener expected struct
```

which permits a listener registered for a base struct to receive derived
payloads, and makes exact equality a special case.

### Type mismatch policy

- log the channel, the sent struct and the expected struct;
- skip that listener;
- never reinterpret incompatible bytes;
- never abort the rest of the broadcast;
- add development-only assertions and tests.

A path that disables the type check entirely — registering with a null expected
type — must be private and documented. If it is reachable from Blueprint through
an empty type pin, it is not private. Recipe: MB-03.

### Payload lifetime

The bus should pass a pointer to the caller's stack object rather than copying.
That is the right performance decision and it creates one hard rule:
**a listener may not retain the payload pointer after its callback returns.**
Copy what you need. Recipe: MB-04.

---

## 4. Exact versus hierarchical matching

Channels are tags, so a broadcast can walk from the sent channel up through its
parents:

```text
Event.Combat.Elimination
→ Event.Combat
→ Event
```

On the first tag every listener is called regardless of match type; on ancestors,
only listeners that registered for partial matching.

**Default to exact.** It minimises accidental traffic and type ambiguity. Use
partial matching for analytics, debug logging, and aggregators that genuinely
want a subtree.

### The hierarchy type gate

Every descendant channel observed through one parent must share a compatible base
payload struct. Otherwise partial matching converts a semantic hierarchy into a
stream of type errors. Document the payload contract at each parent tag — this is
the same rule as parent-tag contracts in `ue-gameplay-tag-governance`, applied to
payload types instead of semantics.

### Cost

Walking parents costs one map lookup per tag depth on **every** broadcast, even
when no partial listeners exist anywhere. If the listener array is copied per
non-empty bucket for mutation safety, that copy includes a callable object per
listener, which may allocate. On a high-frequency channel this is measurable.
Recipe: MB-16.

---

## 5. Broadcast safely under mutation

Callbacks may unregister themselves or others. Copy the listener array before
iterating, then invoke the copy — and then **define the resulting semantics
explicitly**, because they are observable:

- a listener removed during this broadcast may still receive this one message;
- a listener added during this broadcast receives from the next one;
- ordering is not guaranteed and must not be assumed.

Do not let registration order become an accidental priority contract. If removal
uses a swap-with-last strategy, order changes as a side effect of unrelated
unsubscribes. Recipe: MB-11.

---

## 6. Registration forms and ownership

Provide three forms: a raw callable, a UObject member bound through a weak
reference, and a parameter struct for match type and future options.

The trap is that these three are not equally expressive. If the most convenient
form — the UObject member overload — cannot express the match type, then the
match type is effectively unavailable to the code that would most benefit from
it, and a project can ship a fully implemented hierarchical matching feature that
nothing uses. Recipe: MB-05.

### Ownership patterns

| Owner | Retain | Release |
|---|---|---|
| C++ component | handle as a member | `EndPlay` / deinit |
| subsystem | handles in a container | `Deinitialize` |
| feature action | per activation context | on deactivation |
| async operation | inside the action object | completion, cancel or destruction |

**A weak callback is not an unsubscription.** It prevents a call into a dead
object; the listener record and its callable stay in the map, and accumulate.
Recipe: MB-08.

### Teardown must not assert

An accessor that asserts when there is no world is the wrong tool inside
`EndPlay`, `NativeDestruct` or any other teardown path, where the world may
already be gone. Prefer unregistering through the handle, which resolves the
subsystem weakly and no-ops when it is dead. Recipe: MB-09.

---

## 7. Blueprint parity

A wildcard struct pin lets Blueprint send arbitrary payloads while C++ receives a
type plus bytes. An async listen node stores the channel, payload type and match
type, registers on activation, copies the payload into typed output storage, and
unregisters on cancel or destruction.

### Keep the two APIs semantically identical

This is the rule most often broken, because the two paths are written at
different times by different people:

- if C++ accepts derived payloads, Blueprint must too;
- if C++ logs a mismatch, Blueprint must log it as well.

A silent Blueprint skip produces "the node never fires", which every developer
first investigates as a wrong tag. Pick one contract, document it, and test both
APIs against the same matrix. Recipe: MB-02.

---

## 8. Messaging is not replication

No broadcast crosses the network. For networked facts the shape is always:

```text
server-authoritative state change
→ replicated property / RPC / replicated fast array
→ receiving side broadcasts a LOCAL message
→ local UI, feedback and processors react
```

This keeps transport and local fan-out separate, and it is the only arrangement
in which a late joiner is correct: the state replicates, and the message is
merely a notification that it changed.

**Never treat a client-local message as proof of a server-side fact.** A message
may request UI behaviour. It is not evidence of damage, score, ownership or team
membership. Recipe: MB-15.

---

## 9. Payload design

A message struct is a compact immutable fact:

```text
verb / channel context
instigator
target
magnitude
context tags
optional IDs or weak references
```

Rules:

- prefer IDs and weak references over large object graphs;
- carry enough context that a listener needs no callback into the sender;
- do not embed mutable ownership;
- initialise every field — a payload never passes through serialisation, so
  there are no free defaults;
- version deliberately if the same struct is persisted or replicated elsewhere;
- one parent channel hierarchy shares one base payload.

### Do not send commands disguised as events

```text
bad:   message "please give the player a weapon"
good:  service call performs the grant; message "weapon equipped"
```

A command has exactly one accountable handler and a failure result. An event has
zero or many listeners and no failure path at all. Sending a command as an event
means nobody is responsible for it happening, and nobody notices when it does
not. Recipe: MB-14.

---

## 10. Channel naming and the string contract

Name channels so bus traffic is distinguishable from other tags:

```text
<System>.<Domain>.Message[.<Detail>]
```

The word in the middle separates channels from the rest of the vocabulary and
gives a natural place for a partial-match subscription.

**The channel string is the public contract, and the compiler does not check it.**
If publisher and subscribers each declare their own file-local tag constant for
the same string, the engine deduplicates by string and everything works — until
one of them is edited. Put shared channels in one header owned by the publisher.
Recipe: MB-10.

---

## 11. Migration recipe

When decoupling a direct dependency:

1. Name the fact in the past tense.
2. Define its payload struct and channel tag.
3. Keep authoritative mutation in the existing owner.
4. Broadcast only **after** the mutation succeeds.
5. Move independent side effects to listeners, one at a time.
6. Retain and release every handle.
7. Test zero, one and multiple listeners.
8. Verify no late subscriber needs the state it missed.

Good first migrations: combat event to HUD feed and audio; inventory delta to a
notification widget; phase transition to local presentation.

Do not migrate tight request/response code merely to avoid a function reference.

---

## 12. Review checklist

- [ ] Message is an event, not durable state and not a command.
- [ ] Subsystem scope matches the required lifetime.
- [ ] Payload is a struct with a documented contract and initialised fields.
- [ ] Parent channels have a compatible payload hierarchy.
- [ ] Exact matching is the default; partial matching is justified per site.
- [ ] Registration returns a handle and the caller retains it.
- [ ] UObject callbacks bind weakly.
- [ ] Unregistration happens on every lifecycle exit, including teardown paths.
- [ ] Teardown does not call an asserting accessor.
- [ ] Broadcast tolerates mutation from inside a callback.
- [ ] C++ and Blueprint type semantics are identical and both log mismatches.
- [ ] No listener ordering is assumed without an explicit contract.
- [ ] Replication and RPC transport are separate from local fan-out.
- [ ] Shared channel tags live in one owned header.

---

## 13. Tests

### Type matrix

- exact same struct;
- derived broadcast to base listener;
- base broadcast to derived listener — rejected;
- unrelated struct — logged and skipped;
- expired expected struct type;
- C++ and Blueprint produce the same result for every row above.

### Channel matrix

- exact listener, exact broadcast;
- parent with partial matching receives a child broadcast;
- parent with exact matching does not;
- sibling does not;
- a nested parent chain invokes each intended listener exactly once.

### Lifecycle

- unregister before broadcast;
- unregister from inside a callback;
- owner destroyed without an explicit unregister;
- async node cancelled;
- map travel with a GameInstance-scoped bus — listener count returns to baseline;
- feature activation and deactivation cycle, twice;
- duplicate registration is either documented or detected.

### Network boundary

- a server-side broadcast is invisible to clients;
- replicated transport triggers exactly one client-local rebroadcast;
- a listen-server process does not process both the server and client path.

---

## 14. When not to add a bus

Use a direct interface, service or delegate when:

- exactly one receiver must handle the call;
- the caller needs a return value or a failure reason;
- ordering is part of correctness;
- sender and receiver share ownership and lifetime;
- the state must be queryable after the event.

A bus reduces coupling only when the fact genuinely has independent, optional
observers. Used anywhere else it hides control flow and weakens correctness —
it converts a compile-time dependency into a runtime one that nothing verifies.

---

## Provenance

The findings behind the failure modes come from a line-by-line source audit of
the gameplay message router plugin shipped with Epic's Lyra Starter Game on
Unreal Engine 5.6, together with its use in that project. The plugin's runtime
module is roughly a thousand lines and was read in full, which is why several
claims here are negative results ("there is no networking in this module") stated
with confidence rather than hedged.

Source addresses stay in the research archive that produced this skill; what
ships is the detection recipe. Each entry carries a stable identifier (`MB-01`,
`MB-02`, …) that resolves back to the audited location in that archive.

## Evidence boundary

The measured material refers to one plugin at one engine version in one
workspace. Blueprint graphs were not read — they are binary — so every statement
about Blueprint *usage* in that project is bounded by what C++ could show, and is
marked as open rather than concluded. Re-run the recipes against your own tree
before trusting any specific claim.
