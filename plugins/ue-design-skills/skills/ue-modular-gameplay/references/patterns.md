# Patterns: a feature-action layer read end to end

A worked reading of one real modular gameplay implementation: how a feature
attaches behaviour to actors it does not own, and what happens when it detaches.

Individual defects are in [failure-modes.md](failure-modes.md), one entry each,
with a recipe. This file is about the shapes worth copying, and about one
finding that only becomes visible when you count.

Markers: **[measured]** — read in source; **[derived]** — conclusion from measured
facts; **[open]** — not answerable from the available source, and left open.

**A scope caveat that shapes everything below.** The engine-side component
manager, request handle, feature action base and feature subsystem are not part
of the audited project — they live in engine plugins that were not in the tree.
Every statement about them here is inferred from call sites **[derived]**, and is
marked so. This is the honest version of a common situation: you can audit how a
project *uses* an engine subsystem far more cheaply than you can audit the
subsystem, and the usage is where your defects will be anyway.

---

## 1. The core idea: the action does not look for actors

The mechanism that makes this architecture work is one inversion.

A feature action does **not** scan the world for actors to modify. It registers
an extension handler for a target *class* with a component manager, and the
manager invokes that handler for every matching receiver — the ones that already
exist and the ones that appear later **[measured]**.

```text
receiver actor registers itself with the manager
action registers an extension handler for a class
manager invokes the handler for existing AND future receivers
returned request handle owns the subscription
```

The receiver side is three calls, and in the audited project they live in modular
base classes rather than in gameplay code **[measured]**: add receiver in
pre-initialize, send a ready event at begin play, remove receiver at end play.

**[derived]** The consequence is the whole point of the architecture: base
gameplay classes register as receivers and **know nothing about features at all**.
Nothing in the character, player state or game mode references the feature system.
A feature plugin can be added to the project without touching any of them.

The audited project contains one instructive exception. A HUD class inherits a
non-modular engine base, so those three calls are written out by hand in it
**[measured]**. Correct — and fragile in a way the inherited version is not,
because the third call is easy to omit and its omission has no symptom until
something counts registrations. Recipe: MG-16.

---

## 2. Ownership is a reference count, and nothing says so

Handler registration and component requests return shared handles **[measured]**.
There is no explicit unregister call anywhere in the audited code
**[measured]** — the only way to detach is to release the last reference.

Every reset path therefore begins by emptying an array of handles **[measured]**,
and that line *is* the unsubscribe operation even though it reads as ordinary
container cleanup.

**[derived]** Two failure directions follow, and both are quiet. Hold a handle too
long and the subscription leaks. Clear the array early and a live feature detaches
with no event. Reviewing teardown for "removal calls" finds none — correctly,
because there are none — so the reviewer must already know the ownership model to
see that teardown is present. Recipe: MG-17.

One detail in the audited code confirms the model from the inside: when a
component already exists, the action still issues a request for it in some cases,
with a comment explaining that requests are reference counted **[measured]**.
**[derived]** That is a project telling you, in its own code, how the engine
subsystem it depends on behaves — which is the best evidence available when the
subsystem's source is not in the tree.

---

## 3. Per-context state, and why it is not optional

One action object can be active in several state-change contexts at once — client
and server in a single process being the ordinary case. Every lifecycle method
receives a context, and four separate actions in the audited project key their
state by it **[measured]**:

```cpp
struct FPerContextData { /* tracked resources */ };
TMap<FGameFeatureStateChangeContext, FPerContextData> ContextData;
```

This is the pattern to copy verbatim. **[derived]** State in plain member fields
works perfectly with one context and corrupts silently with two, and the second
context's writes look like legitimate updates.

Two supporting habits appear consistently and are worth copying with it
**[measured]**:

- at activation, `ensure` that this context's slot is empty and force a reset if
  not, **before** calling the base implementation — an assertion that converts a
  leak into a visible failure;
- at deactivation, call the base implementation **first**, then reset the
  context's data.

The base class itself keeps its delegate handles in a map keyed the same way
**[measured]**, which is how it supports being active in two contexts at once.

Recipe: MG-10.

---

## 4. Semantic readiness events

A generic "extension added" event means only that the manager knows about the
actor. **[derived]** It does not mean the actor has its pawn data, ability system,
controller, or initialised input — so a handler attached to that event alone will
find its prerequisites missing, return early, and never run again.

The audited project solves this by emitting its own named events at the real
dependency boundaries — abilities ready, bind inputs now **[measured]** — and by
having every handler dispatch on **both** the generic event and the semantic one
**[measured]**:

```text
extension removed / receiver removed  -> remove
extension added   / <semantic event>  -> add
```

**[derived]** Whichever arrives second does the work, so activation order stops
mattering. This is the single most transferable idea in the file, and it costs a
`static const FName` plus one call to emit — no change to the feature
infrastructure is required. Recipe: MG-15.

---

## 5. The finding that only appears when you count

Eight actions were audited. Five have incomplete teardown **[measured]**:

| Action | Attaches | Detaches |
|---|---|---|
| add abilities | grants abilities, attribute sets, ability sets; stores every handle | mostly correct — but two revocation semantics for one resource kind, depending on which field granted it |
| add widgets | pushes layouts, registers extensions, stores handles | reset unregisters extensions and does **not** deactivate layouts; the per-actor path does both |
| add input binding | delegates to a game component | the component's removal method has an empty body |
| add input mapping context | adds contexts to the input subsystem | tracks affected controllers in a container **nothing ever writes to** |
| splitscreen config | votes to disable | correct — decrements the vote |

**[derived]** Read one at a time, each looks like an isolated oversight. Read
together, they are one pattern: **the add path is complete in all eight, and the
remove path is complete in three.** That ratio is the argument for the ownership
ledger in the skill — not a rule someone invented, but the shape the evidence
takes.

Two of these deserve their detail, because the detail is what makes them
recognisable elsewhere.

### The container nobody fills

An action declares a container of the controllers it has affected. An `ensure` at
activation asserts it starts empty. The reset loop drains it correctly. The
reactive path removes from it. **Nothing adds to it** — the function that would
takes the per-context data as a parameter and ignores it **[measured]**.

Four of five operations exist, so any search for "is this container used?"
answers yes emphatically. The one missing operation is the producer.

Two things make this the clearest entry in the file. First, a **sibling action in
the same directory** does it correctly, with `AddUnique` in exactly the place the
broken one omits **[measured]** — so the two files diff against each other.
Second, the original authors left a comment on the broken line stating that the
container is never modified **[measured]**. A known defect that shipped. Recipe:
MG-03.

### The rollback that cannot be written

The input-binding action's teardown iterates its tracked pawns and calls a removal
method on the game component. That method's body is a single TODO comment
**[measured]**.

But the cause is one level further down: the function that creates the bindings
declares the handle array as a **local variable** and lets it go out of scope
**[measured]**, at two separate call sites.

**[derived]** So the removal is not merely unimplemented, it is impossible to
implement without changing the component — the information it would need was
discarded at creation. An estimate of "implement the missing rollback" made from
reading the empty function comes out an order of magnitude low. Recipes: MG-01,
MG-02.

---

## 6. What the reference got right

Stated deliberately, because the section above is not an argument against the
architecture:

1. **Actions do not search for actors.** The extension handler protocol handles
   existing and future receivers uniformly **[measured]**.
2. **Per-context state in all four attaching actions** **[measured]**, with the
   activation-time emptiness assertion.
3. **Reset loops written as drain loops** — "while not empty, take the top,
   remove it" **[measured]** — which survives a removal that mutates the same
   collection. A range-for would not.
4. **Two removal routes, both idempotent**: explicit reset at deactivation, and
   reactive removal when the actor dies first, keyed on whether a record exists
   **[measured]**.
5. **Composition enforced over inheritance.** Validation rejects deriving one
   scripted experience from another and points the author at action sets
   **[measured]**. That is a design rule with a compiler behind it.
6. **Action sets are separate primary assets** with their own bundle data
   **[measured]**, which is what allows them to be loaded alongside the experience
   rather than through it.
7. **A one-frame deferral with a named reason** **[measured]** — it waits for
   startup settings. A delay whose prerequisite is named is debt with a receipt;
   an unnamed one is debt with a timer around it. Recipe: MG-14.
8. **A policy class as the place for pre-activation work.** Logic that must run
   before activation, is process-global rather than per-world, or needs to see all
   of a plugin's actions at once, belongs in a lifecycle observer rather than in an
   action **[measured]**. One action in the audited set is pure data with a getter,
   executed entirely by such an observer **[measured]** — a clean separation worth
   copying.

---

## 7. The authors' own TODO block

The experience manager carries a block of eight TODOs from its authors
**[measured]**, covering: asynchronous experience loading; explicit error
handling instead of assertions; running actions in phases rather than all at
once; support for deactivating an experience; and — stated plainly — that plugins
are **leaked enabled** between experiences, with diffing requirements named as the
intended fix.

**[derived]** This is the cheapest finding in any audit, and the most reliable.
The authors know; they wrote it down; nobody adopting the code reads it, because
adoption reads the class list rather than the comments.

Two practical consequences:

- **Read the TODO blocks first** in any codebase you are adopting. They are a
  defect list written by the people best placed to write one.
- Treat "the authors documented this gap" as *stronger* evidence than a static
  finding of your own, not weaker. It removes the possibility that you have
  misread the intent.

Recipe: MG-12. The same reading also surfaces asynchronous deactivation: pausers
are counted, and when any are outstanding the code logs an error and proceeds
**[measured]**. The limitation is stated in the log text itself. Recipe: MG-19.

---

## 8. Editor loading is not shipping loading

The loading policy loads client data when not a dedicated server, and server data
when not a client-only build **[measured]**. **[derived]** In the editor neither
condition excludes, so both bundle sets load — and the authors noted the resulting
hitching in a comment beside it **[measured]**.

Every in-editor memory and load-time figure therefore describes a configuration
that ships to nobody. Directionally useful, absolutely wrong. Recipe: MG-13.

---

## 9. What source reading could not settle

- **The engine subsystems were not in the tree.** Component manager, request
  handle, feature action base, feature subsystem, and the add-components action
  **[open]**. Everything above about them is inferred from call sites.
- **Binary assets were not read.** Which actions the shipped feature plugins
  actually configure, and with what data, is **[open]**. What *is* measured: those
  plugins contain no feature-action C++ of their own, so they use only actions
  from the base module and the engine **[measured]**.
- **One teardown question is genuinely undecidable from this tree.** Whether
  clearing the handle array causes the manager to dispatch removal events — which
  would make the narrower reset path in MG-04 harmless — depends on engine code
  that was not available **[open]**. It is recorded as an open question rather than
  resolved in either direction, because a plausible answer either way would be a
  guess.

That last item is worth its space. It would have been easy to state MG-04 as a
confirmed defect; the honest form is "this is a defect unless an engine behaviour
we could not read compensates for it", and a reader adopting the code can settle
it in ten minutes with the engine source that they have and the audit did not.

---

## Provenance

Measured against the feature-action layer of Epic's Lyra Starter Game on Unreal
Engine 5.6, read as source in a single workspace. Source addresses stay in the
research archive that produced this skill; each `MG-` identifier resolves back to
the audited location there, so any specific claim above can be produced on
request.

## Evidence boundary

One project, one engine version, one workspace, with the engine-side subsystems
outside the readable tree. These are examples and failure evidence, not
guarantees about other versions. Claims marked open stay open. Re-run the recipes
in [failure-modes.md](failure-modes.md) against your own tree before acting on
anything here.
