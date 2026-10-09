---
name: ue-ui-architecture
description: >-
  Design or review scalable Unreal Engine UI: a root layout per local player,
  tagged layer stacks, extension points for slot-based widget injection from
  feature plugins, input and focus policy per screen, and centrally arbitrated
  loading screens. Use when building HUD, menu or modal architecture, adding
  mode or plugin UI without base-class dependencies, supporting gamepad or local
  multiplayer, or debugging focus, ordering, duplicate-widget and teardown
  issues.
---

# UE UI architecture

The invariant:

> UI ownership, placement and content are separate. The shell owns slots and
> layers; features contribute content through handles and contracts.

Measured patterns from a reference product: [patterns](references/patterns.md).
Detection recipes for silent UI failures: [failure modes](references/failure-modes.md).

Related skills: `ue-modular-gameplay`, `ue-input-architecture`,
`ue-gameplay-messaging`, `ue-gameplay-tag-governance`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. One root layout per local player

```text
UI manager subsystem
└─ UI policy
   └─ primary layout, one per local player
      ├─ UI.Layer.Game
      ├─ UI.Layer.GameMenu
      ├─ UI.Layer.Menu
      └─ UI.Layer.Modal
```

Responsibilities: the **subsystem** is the process-level entry point and owns the
active policy; the **policy** decides which layout class to create, where to
attach it, and how local players behave; the **layout** is a named layer registry
with a push/pop API; **widgets** are content only.

Do not let gameplay systems add widgets to the viewport with a guessed draw
order. A widget that bypasses the layout is invisible to every mechanism the
layout provides — visibility toggles, input suspension, focus restoration.

### Let the base subsystem stand aside

A base UI subsystem should decline to be created when a project subclass exists,
so the two never coexist. The idiom — *do not create me if I have derived
classes* — is worth copying anywhere a plugin offers a replaceable subsystem.

### Local players own their UI

Each local player needs an independent layout, focus state and input routing. One
global HUD root breaks split-screen and player-specific modal stacks, and the
breakage appears only when a second player joins.

---

## 2. Tagged layer stacks

Layers express **modality**, not individual screens:

| Layer | Use |
|---|---|
| Game | HUD and persistent gameplay presentation |
| GameMenu | pause and in-game menus |
| Menu | front-end navigation |
| Modal | confirmations, errors, blockers |

Each layer is an activatable widget stack: screens are pushed by soft class,
activated and deactivated, and popped by lifecycle.

### Rules

- register each layer tag exactly once per layout;
- no screen hard-codes a sibling widget path;
- the modal layer carries the strongest input and focus policy;
- popping restores the previous screen and its focus;
- async load failure reports a reason and clears any loading state;
- **pushing to an unregistered layer tag must not fail silently.** A typo in a
  layer tag that returns null with no log is a screen that never appears and
  nothing to search for. Recipe: UI-04.

### Layers are not draw-order buckets

If two widgets belong to one HUD composition, use extension slots inside the HUD
layout. Inventing `UI.Layer.HUDLeft` and `UI.Layer.HUDRight` turns a modality
concept into a layout concept and loses both.

---

## 3. Extension points decouple slot owners from contributors

A subsystem holds two maps keyed by tag:

```text
extension point tag → registered points
extension point tag → registered extensions
```

**A point** is owned by a shell widget: its tag, an optional context object, the
data or widget classes it accepts, its tag match mode, and a callback.

**An extension** is owned by a feature: the target tag, an optional context, a
data object or widget class, and a registration handle.

### Registration must be order-independent

Both sides catch up on registration — a new point receives already-registered
matching extensions, and a new extension notifies already-registered matching
points. This is what removes initialization-order coupling between the HUD and
feature activation, and it is the single most valuable property of the pattern.

### Both sides copy before iterating

Callbacks can register or unregister anything, including themselves. Copy the
list before notifying, and define what happens to an entry removed mid-notify.

---

## 4. Contract matching

An extension matches a point when all applicable rules pass:

1. **tag** — exact, or ancestor-ward for partial matching;
2. **context** — same object, or both explicitly global;
3. **class contract** — the data derives from, or implements, an allowed class;
4. **ownership** — local player and world are compatible.

### Context tiers

One slot widget can register points for the global context, for its local player,
and for that player's player state. The same slot tag then serves global HUD
elements and player-specific elements with no cross-player leakage — and
split-screen works without a special case.

### Know which direction partial matching runs

Ascending from the extension's tag to its ancestors means a point tagged `A.B`
with partial matching receives an extension tagged `A.B.C`. **The reverse does
not happen.** Prefer exact tags for production HUD placement, and give every
parent tag used for partial matching a coherent data contract.

### A dead context object is not a global context

If context matching compares pointers and the context is held weakly, an
extension whose context died matches nothing at all — it does not fall back to
global, and it does not clean itself up. It sits in the map until someone
unregisters it. Recipe: UI-06.

---

## 5. The slot widget owns rendering

The slot widget registers and unregisters points, converts extension data into
entry widgets, discovers its context, enforces the class whitelist, and defines
empty-state behaviour.

The feature does not find the slot and does not add children. It registers an
extension and retains the handle. That is dependency inversion:

```text
feature knows: tag + widget class
shell knows:   tag + layout container
neither knows the other's concrete type
```

Register in the widget's build step rather than its constructor, and unregister
when Slate resources are released — otherwise a rebuilt widget leaves a
registration behind.

---

## 6. Feature-driven UI has two distinct paths

**Layout requests** push an activatable screen into a layer.
**Element extensions** register a widget into a named slot.

They are different mechanisms with different removal semantics, and putting both
in one feature action is convenient and dangerous. Retain separately: handles to
pushed layouts, an extension handle per slot registration, actor extension
request handles, and per-actor ownership records.

### The two teardowns are not equivalent

Unregistering an extension handle removes the entry widget **synchronously**.
Deactivating a layout **asks** the stack to release it. Do not assume the second
is removal — verify the stack no longer retains or reactivates it. Recipe: UI-05.

Removal must also be keyed to the specific actor that was registered: more than
one HUD actor can be alive on a client at once.

---

## 7. Ordering must be a real contract

If the API exposes a priority, the implementation must sort or insert by it.
**Copying a priority into a request does not create ordering.**

Define: which direction wins; the tie-break for equal values; whether priority is
per point, per tag, or per context; what happens when it changes; and who owns
the sort — the subsystem or the slot widget.

Where ordering is unimplemented, the effective order is registration order, which
in a plugin-based project is feature activation order — non-deterministic from the
designer's point of view, and made worse by any removal that swaps elements.
Recipe: UI-01.

---

## 8. The loading screen is arbitration, not a layer

A loading screen sits above the entire UI, including the root layout. A manager
aggregates reasons from objects implementing a loading-process interface:

```text
ShouldShowLoadingScreen(out Reason) → bool
```

Blockers typically include: experience or mode still loading, map travel, pending
network game, world not begun, seamless travel, missing player controllers, and
explicitly registered async tasks.

Manager behaviour: inspect all providers, show while any blocker exists, retain a
human-readable reason, enforce an optional minimum display time, hide when clear,
and survive world teardown.

### Rules

- providers report need and reason; the manager owns presentation;
- no subsystem toggles the loading widget directly;
- **require a non-empty reason.** The reason string is the only diagnostic that
  answers "why is this screen still up";
- stale tasks have a timeout, a cancel path and an owner;
- editor and packaged behaviour are both tested — an input blocker that is
  disabled in the editor means the editor is not testing the shipped behaviour.
  Recipe: UI-08;
- **measure before copying performance side effects.** Forcing garbage collection
  when the screen hides puts a hitch exactly at the moment control returns to the
  player. Recipe: UI-07.

---

## 9. Input and focus policy per screen

Each activatable screen declares its input configuration: game-only, menu-only or
both; mouse capture and cursor behaviour; a desired focus target; back-action
handling; whether lower layers receive input.

The framework owns the activation stack, focus restoration, gamepad navigation,
the bound-action bar, and input suspension during transitions.

### Validate what the compiler cannot

- **every activatable screen has a desired focus target.** A screen without one
  opens and leaves the gamepad with nowhere to go. If your framework only warns
  about this, treat the warning as an error — a screen with no focus is not
  shippable. Recipe: UI-09;
- the input configuration matches the layer's role;
- a required back action exists;
- no raw key handling bypasses the UI input system;
- extension point contracts are non-empty where required.

### Transitions and focus interact

A non-zero stack transition duration can break focus hand-off to the incoming
screen on a gamepad. If you disable transitions to fix focus, write down that
this is why — otherwise someone will re-enable them.

---

## 10. The communication boundary

UI may listen to local messages for **transient facts**: an elimination for the
feed, an accolade for a toast, an inventory delta for a notification.

Persistent display reads **observable state**: health, score, inventory,
settings. Do not rebuild state from a stream of messages — a widget created
mid-match will have missed them. See `ue-gameplay-messaging`.

UI sends commands through accountable controllers and services, never as a
broadcast with no owner.

---

## 11. Test matrix

### Extension ordering

Point first then extension; extension first then point; several points with
distinct contexts; global plus local-player plus player-state points;
unregistering an extension while its point lives; destroying a point before the
extension's owner.

### Modular lifecycle

```text
baseline HUD
→ activate feature  → exactly one layout, one entry per extension
→ deactivate        → back to baseline, verified not assumed
→ reactivate        → no duplicates
```

### Local players

One player; split-screen; adding and removing a player at runtime; confirming
player-specific context does not leak; independent modal and focus stacks.

### Input and focus

Keyboard and mouse; gamepad navigation; device hot-swap; back through nested
stacks; modal blocking lower layers; the loading screen capturing input **in a
packaged build**; focus restored after a pop.

---

## 12. Review checklist

- [ ] One root layout per local player.
- [ ] Every screen enters through a named layer.
- [ ] HUD contributions use extension slots, not direct widget references.
- [ ] Registration order is irrelevant in both directions.
- [ ] Context and class contract are explicit at every point.
- [ ] Features retain extension, layout and request handles.
- [ ] Deactivation removes layouts and entries completely, verified.
- [ ] Ordering is deterministic, or documented as unspecified.
- [ ] Pushing to an unknown layer tag is loud.
- [ ] The loading screen is centrally arbitrated and every reason is non-empty.
- [ ] Every activatable widget has a desired focus target.
- [ ] Device presentation stays in the input/UI layer.
- [ ] Persistent display reads state; only transient facts come from messages.
- [ ] Split-screen behaviour is tested, not assumed.

---

## 13. When to simplify

For a small single-player game with one fixed HUD and no modular modes, a root
widget with a few direct child references is enough and this indirection is
overhead.

Introduce layers and extension points when at least one applies: plugins or modes
add UI independently; local multiplayer is required; modal, menu and game input
policies conflict; screens need async loading and a stack; contributors must not
depend on the shell widget class; gamepad focus restoration must be systematic.

The goal is not maximum indirection. It is explicit ownership and replaceable
placement contracts — and the cost of that is a debugging path that crosses
several assets, which you pay every time something does not appear.

---

## Provenance

The findings behind the failure modes come from a line-by-line source audit of
the UI layer of Epic's Lyra Starter Game on Unreal Engine 5.6: the extension
subsystem, the layer and policy plugins, the loading-screen plugin, and the
project's own widgets and feature action.

The framework the project sits on — the activatable widget stack, focus
management, the input subsystem — was **not** in the audited tree, so every
statement about it is inferred from call sites and is marked as such rather than
presented as measured. Widget blueprints are binary and were not read.

Source addresses stay in the research archive that produced this skill; what
ships is the detection recipe. Each entry carries a stable identifier (`UI-01`
and up) that resolves back to the audited location.

## Evidence boundary

One project, one engine version, one workspace. Layer-to-container binding lives
in binary assets, so which layers actually exist in that project is out of scope
rather than concluded. Re-run the recipes against your own tree before acting on
any specific claim.
