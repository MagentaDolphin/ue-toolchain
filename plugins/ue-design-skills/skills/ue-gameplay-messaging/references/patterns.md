# Patterns: a message bus read line by line

A worked reading of one real tag-addressed message bus and its use in the product
that ships it. The runtime module is about a thousand lines and was read in full,
which is why several claims below are **negative results stated with confidence**
rather than hedged — "there is no networking in this module" is a conclusion from
reading every line of it, not from a search that found nothing.

Individual defects are in [failure-modes.md](failure-modes.md), one entry each,
with a recipe. This file is about the shapes: what the bus is, where its costs
sit, and how the surrounding product worked around what it does not do.

Markers: **[measured]** — read in source; **[derived]** — conclusion from measured
facts; **[open]** — not answerable from source, and left open.

---

## 1. What the mechanism actually is

A publish/subscribe bus where the **channel is a tag** and the **message is an
arbitrary struct**. Publisher and subscriber never reference each other; the
entire contract is the pair (channel tag, struct type).

The implementation is one flat map from tag to listener list **[measured]**.
There is no tag tree in the data structure — hierarchy is walked at broadcast
time by asking each tag for its direct parent until the chain ends.

Two properties fall out of that design and explain most of this file:

1. **The join is a string and a reflection pointer.** Neither is checked by the
   compiler. Everything in the failure-mode list is a consequence.
2. **Delivery is synchronous.** Callbacks run inside the broadcast call before it
   returns **[measured]**. Good for debugging — the stack is continuous — and the
   reason reentrancy is possible at all.

The module's dependencies are the engine core, the engine, and the tag system
**[measured]**. Nothing from the game, nothing from the ability system. **[derived]**
That self-containment is why this kind of plugin is worth lifting wholesale, and
why its defects travel with it.

---

## 2. Type safety is real, and has exactly one hole

The payload crosses the bus as an untyped pointer plus a reflected struct type.
The gate is one line **[measured]**: deliver when the listener never had a valid
type, **or** when the sent struct derives from the listener's expected struct.

That gives three branches, and they are not equally safe:

| Branch | Behaviour | Assessment |
|---|---|---|
| Sent type derives from expected type | delivered | correct, and makes exact equality a special case |
| Types unrelated | logged as an error, listener skipped, broadcast continues | correct and loud |
| Listener registered with no expected type | **check bypassed entirely** | documented "for internal use" — and reachable from a Blueprint node with an empty type pin **[measured]** |

The third row is the hole. What makes it interesting is not that it exists — an
internal escape hatch is a reasonable thing to have — but that the comment
asserting it is internal is the only thing protecting it **[derived]**. In the
Blueprint path a second, stricter check downstream limits the damage to a failed
payload extraction. In C++ the same registration combined with a templated
callback would reinterpret unrelated bytes with no diagnostic at all. Recipe:
MB-03.

There is also a defensive feature worth copying: the expected struct type is held
weakly, with a flag recording that it was once valid, so a listener whose struct
was garbage collected is detected and removed at broadcast time with a warning
**[measured]**. Epic's own comment on those two fields says they were added in
response to real problems. **[derived]** That is a project that was bitten and
responded structurally — and the removal code it added is where MB-01 lives.

---

## 3. The defect worth reading twice

During the parent walk, a stale listener is removed using the **original
broadcast channel** rather than the ancestor tag currently being visited
**[measured]**. Handle IDs are unique only within a channel.

This entry earns its place because of *where* the mistake is, not what it does:

- the loop header three lines up rebinds what "the channel" means on every
  iteration;
- the error-log statement a few lines **below** the bug uses the loop variable
  correctly **[measured]**;
- so the same function contains both the right and the wrong idiom, and the wrong
  one is the one that mutates state.

**[derived]** Two outcomes, both quiet. Either nothing is found and the warning
repeats on every subsequent broadcast forever, or an unrelated listener holding
the same channel-local ID in the broadcast channel's bucket is removed instead,
and its owner silently stops receiving.

It requires hierarchical matching plus an expired struct type simultaneously, so
the audited project never hits it — its own usage has neither. **That is exactly
why it matters to someone lifting the plugin**: the conditions that make it
harmless are properties of the original product, not of the code. Recipe: MB-01.

---

## 4. A fully built feature that nothing uses

Hierarchical matching is implemented in the broadcast walk, exposed in the enum,
and selectable in the Blueprint node **[measured]**. Game-code usage: **zero**
**[measured]**.

The cause is one unforwarded default argument. The overload that binds a UObject
member weakly — the safest form, and the one used almost everywhere — delegates to
the raw form without passing the match type, so it is always exact **[measured]**.
Reaching hierarchical matching from C++ requires switching to a lambda or an
options struct, for reasons the API never states.

**[derived]** The general shape is worth more than the instance: **a feature can
be complete, correct, tested and documented, and still be unreachable from the
path everyone actually uses.** Auditing for "is it implemented?" finds it.
Auditing for "who calls it?" finds the truth. Recipe: MB-05.

Two neighbouring subsystems in the same product had independently copied the
channel-tag-plus-match-type pattern **[measured]** — evidence that the idea was
considered good enough to reproduce, in a project where the original was never
switched on.

---

## 5. Blueprint parity is where the asymmetries live

The scripting layer is a separate module, editor-only, with its own node
**[measured]**. It does several things well: a wildcard output pin retyped from
the selected payload struct, a compile-time error when a wildcard payload pin is
connected but untyped, and a copy of the payload by value at the boundary so
scripting never holds the sender's stack pointer **[measured]**.

And then the two paths disagree about types **[measured]**:

| | C++ | Blueprint |
|---|---|---|
| Type gate | derived accepted | strict equality |
| Mismatch | logged as an error | **silent skip** |

**[derived]** A Blueprint listener on a base struct silently misses derived
payloads that its C++ equivalent receives, and reports nothing. The observable is
"the node never fires", which everyone investigates as a wrong tag first, because
that hypothesis is cheap to test.

Neither behaviour is wrong on its own. They were written for different consumers
and each is correct against its own local reasoning; nothing in either file
mentions the other. **The rule that would have caught it is procedural, not
technical: one test matrix, run through both APIs.** Recipe: MB-02.

---

## 6. Lifetime: three separate ways to leak

| Shape | Measured | Consequence **[derived]** |
|---|---|---|
| Listener map cleared only at GameInstance teardown | reset appears in `Deinitialize` and nowhere else | Records from a travelled-away world persist for the session. Weak binding stops the calls, not the accumulation. MB-08 |
| Async node detects owner death only while handling a message | cleanup keyed on the delegate being unbound, inside the message handler; authors' own TODO records the limitation with a tracker ID | On a quiet channel, cleanup waits for traffic. MB-07 |
| Options-struct registration with no bound callback | returns a default invalid handle, no log | A listener that never fires, in code that reads as wired. MB-06 |

The first row generalises past this plugin: **a weak callback is not an
unsubscription.** It prevents a call into a dead object and leaves the record.
Any bus that binds weakly and never sweeps will accumulate, and the accumulation
is invisible precisely because weak binding made it harmless.

The second row is a good example of a finding you should *want* to discover:
the authors documented the limitation themselves, in a comment, with a reference.
A TODO that names the problem is the strongest confirmation available from
reading source.

### And a teardown hazard on the consumer side

The static accessor resolves the world in assert-on-failure mode and then asserts
on both the world and the subsystem **[measured]**. Three consumer classes in the
product call it from destruction paths **[measured]** — where the world may already
be gone — when unregistering through the handle would have resolved the subsystem
weakly and no-opped. **[derived]** Correct in every ordinary shutdown; an assert
in the unusual orders that nobody can reproduce on demand. Recipe: MB-09.

---

## 7. How the product worked around no networking

The bus has no networking at all: no server, client or multicast functions, no
custom serialisation, no replicated properties **[measured]**, in a module small
enough to have been read in full. The surrounding product needed networked facts
anyway, and solved it three ways — worth comparing, because they are not equally
good.

**1. RPC wrappers on game state and player state.** A multicast or client-targeted
RPC receives the message struct and, on arrival, rebroadcasts it locally
**[measured]**. The rebroadcast is guarded by a net-mode check so a listen server
does not process both the server-side publication and the client-side
rebroadcast **[measured]**. That guard is the transferable part; without it every
listen-server host sees everything twice. The headers say plainly that these are
for notifications that can be lost.

**2. A replicated fast array that rebroadcasts on arrival.** Fully implemented and
**used nowhere in the project** — no member of that type exists anywhere
**[measured]**. It is a worked example rather than working code, and it carries an
empty removal callback (see the network-authority skill for why that matters at
adoption time).

**3. Replicated state plus a local broadcast on the replication callback.** The
cleanest and the most used **[measured]**. State replicates; the message is purely
a local notification that it changed.

**[derived]** The third pattern is the one to copy, and the reason is the
state-versus-event test: only in that arrangement is a late joiner correct,
because the truth is in the replicated state and the message carries none of it.

---

## 8. What the bus does not do, stated plainly

Read as a list of things you will otherwise discover one at a time:

- **No sticky or replay messages.** A subscriber cannot ask for the last value.
  The product compensates by having new widgets read the owning component
  directly on construction **[measured]** — which only works because the state has
  an owner. MB-13.
- **No ordering guarantee.** The authors say so in a header comment, and removal
  by swap-with-last actively reorders the array **[measured]**. MB-11.
- **No per-player filtering.** Consumers filter inside the callback, comparing a
  target field against their own owner **[measured]**.
- **No cancellation.** Every matching listener receives every message.
- **No recursion guard.** Broadcasting from inside a callback is supported and
  used deliberately by an aggregator in the product **[measured]**; nothing bounds
  the depth if the channel graph ever contains a cycle. MB-12.
- **No thread safety.** Game thread only **[measured]**.
- **No networking.** §7.

---

## 9. The architecture it made possible

Worth stating, because the failure-mode list above is not an argument against the
pattern:

```text
ability system  --damage / elimination-->
    processors in a feature plugin  --assist / chain / streak-->
        scripted relay  --notification-->
            UI widget
```

No layer references the next **[measured]**. The processors live in a feature
plugin that the base module has never heard of, and they are added and removed
with the feature. **[derived]** That is the whole case for a bus: it let
game-mode-specific logic move into a shippable plugin without creating a single
reference from the base module.

Note also the vocabulary discipline that came with it: channels named so bus
traffic is distinguishable from other tags, tags declared next to the publisher,
payload fields initialised at declaration because a payload never passes through
serialisation and gets no free defaults **[measured]**.

And the cost of that discipline, measured: one elimination channel string was
declared independently at **four** sites — the publisher and three processors
**[measured]**. It works because the engine deduplicates by string. **[derived]**
It means the string is the real contract and a single-site edit detaches one
participant silently. Recipe: MB-10.

---

## 10. What source reading could not settle

Stated because it bounds several claims above:

- **Blueprint call sites are invisible to text search.** Three RPC wrappers and
  one notification channel have zero C++ callers or publishers, and all are
  script-callable **[measured]**. Whether they are used, and by what, is
  **[open]**. They are recorded as open questions, not as dead code.
- **The extent of scripted bus usage is unknown.** A search for the listen node
  across all source returns nothing **[measured]**, which means the entire
  scripted traffic of the bus lives in binary assets.
- **The channel-key defect was found by reading, not by running.** It has not been
  reproduced at runtime **[open]**, and its trigger conditions do not occur in the
  audited project.

---

## Provenance

Measured against the gameplay message router plugin and its consumers in Epic's
Lyra Starter Game on Unreal Engine 5.6, read as source in a single workspace. The
runtime module was read in full, line by line; the negative results in §7 and §8
rest on that rather than on a search.

Source addresses stay in the research archive that produced this skill; each
`MB-` identifier resolves back to the audited location there, so any specific
claim above can be produced on request.

## Evidence boundary

One plugin, one engine version, one workspace. These are examples and failure
evidence, not guarantees about other versions. Binary assets were not read, so
every statement about scripted *usage* is bounded by what source could show and is
marked open where it is open. Re-run the recipes in
[failure-modes.md](failure-modes.md) against your own tree before acting on
anything here.
