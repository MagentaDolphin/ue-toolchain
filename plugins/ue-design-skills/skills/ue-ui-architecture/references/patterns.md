# UI architecture patterns: a worked analysis

This is the shell-and-contributor model applied end to end in one shipped
product, with the parts worth copying separated from the parts worth knowing
about.

Individual defects live in [failure modes](failure-modes.md), one entry each with
a detection recipe. This file is about the shape: what each layer owns, why the
seams are where they are, and what it costs.

---

## 1. Three things that are usually conflated

Most UI trouble in a modular project comes from treating these as one concern:

| Concern | Owner | Changes when |
|---|---|---|
| **Modality** — does this block input, capture focus, dismiss on back | the layer stack | a screen opens or closes |
| **Placement** — where on screen this element sits | the slot inside a layout | the layout is redesigned |
| **Content** — what the element is | the contributor | a feature ships |

A single root widget with direct child references collapses all three into one
asset. That asset then belongs to everyone, which means it belongs to nobody, and
every feature branch touches it.

The split that works: **the shell owns modality and placement; features own
content and reach the shell only through tags.**

---

## 2. Layers: modality, not z-order

Four layers cover almost every product:

```text
UI.Layer.Game       HUD and persistent gameplay presentation
UI.Layer.GameMenu   pause and in-game menus
UI.Layer.Menu       front-end navigation
UI.Layer.Modal      confirmations, errors, blockers
```

Each is an activatable widget stack, not a canvas slot. Pushing a screen
activates it and deactivates the one below; popping restores the previous
activation and its focus.

**The rule that keeps this honest:** if you are tempted to add
`UI.Layer.HUDLeft`, you are using layers as z-order buckets. Two widgets in one
HUD composition belong in extension slots inside the HUD layout, not in separate
layers. Layers are for things that change what input means.

### The root layout is per local player

One root layout per local player, each with its own layer map, its own focus
state and its own modal stack. A single global HUD root cannot support
split-screen and cannot give two players independent confirmation dialogs. This
is cheap to build in from the start and expensive to retrofit.

### Registration comes from data, not from code

Layers register themselves by tag from the layout asset rather than being
hardcoded. That keeps the shell designer-editable — and it means no C++ search
can tell you which layers actually exist. Write them down somewhere a human
reads, because the tag list in configuration is the closest thing to a registry
you will have.

---

## 3. Extension points: dependency inversion by tag

The subsystem holds two maps:

```text
ExtensionPointTag → registered points       (slots that exist)
ExtensionPointTag → registered extensions   (content wanting a slot)
```

A **point** is owned by a shell widget: a tag, an optional context object, a
whitelist of accepted classes, a match mode, and a callback. An **extension** is
owned by a feature: a target tag, an optional context, a widget class or data
object, and a handle it must keep.

Neither side names the other. The only shared vocabulary is the tag.

### Registration must be order-independent

This is the property that makes the pattern usable, and it costs two lines:

- a newly registered point immediately receives all matching extensions that
  already exist;
- a newly registered extension immediately notifies all matching points.

Without both directions, whether a feature's widget appears depends on whether
the feature activated before or after the HUD was constructed — which in a
plugin-based project is not deterministic.

### The contract has three clauses

An extension matches a point when all of these hold:

1. **tag** — exact, or the point matched a parent of the extension's tag;
2. **context** — both explicitly global, or the same object;
3. **class** — the data derives from, or implements, something on the point's
   whitelist.

The class check has one subtlety worth copying: if the registered data *is* a
class object, use it directly; otherwise use the class of the instance. That one
branch is what lets "a widget class" and "a data object" travel through the same
registry.

### Context tiers are what make split-screen work

A slot widget registers the same tag three times: once globally, once for its
local player, once for that player's player state (subscribing for the player
state if it has not arrived yet, and firing immediately if it has).

The result is that one slot tag serves global HUD elements and player-specific
elements with no cross-player leakage, and no feature has to know which kind it
is contributing.

---

## 4. What the slot widget owns

The container that renders a slot owns registration and unregistration, the
conversion of extension data into entry widgets, entry creation and removal,
context discovery, the class whitelist, and empty-state layout.

The feature does not find the slot and does not add children to it. It registers
and keeps a handle.

Two modes fall out of this naturally:

- **class mode** — the extension is a widget class; the slot instantiates it;
- **data mode** — the extension is a data object; the slot asks a factory which
  widget class fits, creates it, and then configures it with the data.

Data mode is what makes a HUD list data-driven — the same slot renders whatever
the feature describes, and the widget choice is a lookup rather than a branch.

### Register in the build step, not the constructor

Registration belongs where the widget's underlying Slate widget is built, and
unregistration belongs where those resources are released. Registering in a
constructor registers a design-time object; registering in construction-time
callbacks that do not pair with a release path leaks.

---

## 5. The feature action has two different jobs

A feature that contributes UI does two unrelated things, and conflating them is a
common source of teardown bugs:

```text
LayoutClass → UI.Layer.Game        pushed onto a stack
WidgetClass → HUD.Slot.Reticle     registered into a slot
```

They need separate bookkeeping — handles to pushed layouts, extension handles for
slots, actor extension request handles — and they come off by **different
mechanisms**. In the measured reference, slot extensions unregister synchronously
and completely, while pushed layouts are asked to deactivate and left for the
stack to dispose of. Both are defensible; treating them as the same operation is
not.

### Attach to the shell actor through the extension protocol

Do not search the world for the HUD. Register a handler for the HUD actor class
with the component manager and react to both the generic extension event and the
shell's own ready event. That covers both orderings — feature before shell, shell
before feature — without a retry loop.

### Assets must already be loaded

Feature actions typically resolve soft class references with a non-loading
accessor, relying on the client asset bundle to have loaded them. That is the
right performance choice and it has a failure mode: if the bundle did not load,
the widget silently does not appear. Mark the bundle at the declaration, and
prefer a code path that logs when the accessor returns null over one that passes
null onward.

---

## 6. Ordering is a contract or it is nothing

If the API exposes a priority field, the implementation sorts by it. If it does
not sort, the field is a lie with a plausible name — and in the measured
reference it is exactly that: stored, copied into the request, never compared
(recipe UI-01).

Before shipping an ordering field, define:

- whether higher or lower wins;
- what happens for equal values;
- whether ordering is per point, per tag, or per context;
- what happens when an extension changes priority after registration;
- who owns the sort — the subsystem or the container.

If ordering does not matter, do not expose the field. An unimplemented ordering
knob costs more than no knob, because designers will spend a day tuning it.

---

## 7. Loading screens are arbitration, not a layer

A loading screen sits above everything, including the root layout, and it is not
pushed onto a layer. The manager polls every registered participant:

```text
ShouldShowLoadingScreen(out Reason) → bool
```

Participants: the experience or mode loader, the front-end flow, travel and
session state, and explicitly registered tasks. The manager owns presentation;
participants only report need and reason.

**Two properties are worth copying verbatim.**

*Every reason is a human-readable string, and the helper asserts it is non-empty.*
This is the single best diagnostic in the whole UI stack: when a loading screen
hangs, one query answers "why", and it answers in words.

*The screen holds for a configurable extra period after the last blocker clears,
with world rendering re-enabled during the hold* — so streaming has time to catch
up and the player does not arrive to a texture pop. Note the documented gap: if a
new blocker appears during the hold, the rendering flag is not restored.

Costs to measure rather than inherit: the manager polls every frame through a
long chain of checks, and hiding the screen may force a full garbage collection —
a guaranteed hitch at exactly the moment control returns to the player
(recipe UI-07).

---

## 8. Input and focus belong to the screen

Each activatable screen declares its own input configuration: game-only,
menu-only or both; mouse capture behaviour; desired focus target; back action.
The stack applies the configuration of whatever is on top.

This is what makes "HUD means game input, menu means UI input" a declarative
property rather than imperative code sprinkled through open and close handlers.

### The gamepad failure nobody catches in review

A screen with no desired focus target opens, and the gamepad has nothing to move
from. The player is stuck with a visible screen and no way to interact.

The mitigation worth copying is an editor-time validation that warns when a
screen subclass does not implement the focus-target hook. Note what it is: a
**warning**, not an error. A screen with no focus target still compiles and still
ships (recipe UI-09). If gamepad support matters, promote it.

### Transitions and focus interact

Stack transition animations can break focus hand-off to the incoming screen. The
measured reference sets transition duration to zero at layer registration, with a
comment explaining exactly that. The consequence — the product has no screen
transition animations at all — is a real design cost, accepted deliberately.
Know that you are making the same trade.

---

## 9. What UI may read, and what it may not

UI may subscribe to local messages for **transient facts**: an elimination for
the feed, an accolade for a toast, an inventory delta for a notification.

UI reads **state** from an observable model: health, score, inventory contents,
settings.

The line: do not rebuild state from a stream of events. A widget created after
the third elimination must show the correct score, and a message-derived counter
cannot promise that.

In the other direction, UI sends commands through an accountable service or
controller, not as a broadcast. "Please equip weapon" with no named handler has
no failure result and no owner.

---

## 10. Costs of this architecture

Stated plainly, so the decision is informed:

- **Indirection.** Finding "what draws this HUD element" means following a tag
  through a registry rather than a reference through an asset. There is no
  "find references" for a tag.
- **No compile-time check on the join.** A slot with a typo in its tag renders
  nothing and reports nothing. Same for a contributor.
- **Runtime debugging is push-based.** If the subsystem exposes no query of its
  current registrations, the only tool is verbose logging.
- **World-scoped registries do not survive travel.** Correct for
  feature-scoped UI, wrong for anything that must persist across maps.
- **Order is not guaranteed** unless you implement it (§6).

### When to simplify

A single-player game with one fixed HUD, no local multiplayer and no modular
modes does not need this. A root widget with direct children is honest and
smaller.

Introduce layers and extension points when at least one is true: plugins or modes
add UI independently; local multiplayer is required; screens need distinct input
policies; screens load asynchronously and stack; contributors must not depend on
the shell widget class; gamepad focus restoration must be systematic.

---

## Provenance

The analysis above comes from a line-by-line audit of the UI stack of Epic's Lyra
Starter Game on Unreal Engine 5.6 — its extension subsystem, its layer and policy
plugins, its loading screen plugin, and the game module that consumes them — read
as source rather than run.

Two boundaries applied to that reading and apply to these claims: the engine's
own CommonUI implementation is not part of that project, so statements about
focus and activation internals are inferred from usage rather than read; and
widget assets are binary, so the concrete layout of any screen was not inspected.

Source addresses stay in the research archive that produced this skill. Entry
identifiers in [failure modes](failure-modes.md) resolve back to the audited
locations, so any specific claim can be produced on request.

## Evidence boundary

One project, one engine version, one workspace. The architecture is transferable;
the specific defects are evidence, not guarantees about other versions. Re-run
the detection recipes against your own tree before acting on any specific claim.
