---
name: ue-cosmetics-and-teams
description: >-
  Design or review modular character cosmetics and team systems in Unreal
  Engine: replicated cosmetic intent with local realization, controller-owned
  selection versus pawn-owned realization, fast-array entries, dedicated-server
  exclusion, tag-driven mesh and animation selection, one authoritative team
  identifier with subscribed mirrors, team relationship and damage policy, and
  data-driven material presentation. Use when building skins, modular
  characters, team assignment, friendly fire, hit-marker filtering or
  team-coloured UI and effects.
---

# UE cosmetics and teams

Two invariants, one per half:

> Replicate cosmetic **intent**, never the spawned presentation.

> Store team membership **once**, authoritatively; every other copy is a mirror
> with a subscription.

Measured patterns from a reference product: [patterns](references/patterns.md).
Detection recipes: [failure modes](references/failure-modes.md).

These two systems are in one skill because they meet at exactly one point —
presentation — and the most common design error is letting them meet anywhere
else.

Related skills: `ue-data-driven-architecture`, `ue-gas-architecture`,
`ue-gameplay-messaging`, `ue-modular-gameplay`, `ue-multiplayer-authority`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

# Part I — Modular cosmetics

## 1. Split persistent intent from pawn realization

A controller-level component owns the selection, so it survives pawn death and
respawn. A pawn-level component realizes it on the current body.

```text
controller component            pawn component
├─ desired part list            ├─ replicated part list
├─ listens for pawn changes     ├─ spawns local presentation components
└─ applies and removes on the   ├─ computes cosmetic tags
   current pawn, keeping        └─ notifies body and animation selection
   handles
```

If the only record of a player's appearance lives on the pawn, it dies with the
pawn. That is the whole reason for the split.

### Possession transfer

On a possession change, in this order: remove owned parts from the old pawn;
find the component on the new pawn; add owned parts; retain the returned handles.
**Each owner removes only its own parts** — cheats, developer settings and real
content coexist in one list, distinguished by a source field rather than by
separate lists.

---

## 2. Define a part as data, and make it incapable of gameplay

A minimal part: a class to spawn, a socket to attach to, and a collision mode
that defaults to none.

Default presentation safety: collision off unless explicitly requested; no
ability system, attributes or authority inside the cosmetic actor; no replicated
gameplay state; validated attach target; locally tracked handle.

### The guarantee is the net-mode guard, not the convention

Nothing in the type system prevents putting a gameplay-capable actor into a part
class. The real isolation comes from one line: **presentation is not spawned at
all on a dedicated server.** The server therefore cannot trace against, collide
with, or be influenced by cosmetics, because they do not exist there.

Be precise about the limit of that guarantee: on a listen server or in
standalone, the parts *do* exist on the authority. Recipe: CT-01.

---

## 3. Replicate intent with a fast array

The replicated entry holds the intent — class and socket. It must not hold the
local handle or the spawned component. Put both of those in the same struct as
**non-replicated** fields and let the annotation express the split, rather than
maintaining two parallel types.

Callbacks realize changes locally: post-add spawns, pre-remove destroys,
post-change rebuilds.

### Decide what "change" means before you need it

A common and defensible implementation makes post-change destroy and respawn the
actor, because propagating a diff into an already-spawned actor is hard. That is
fine and it is a decision with a cost: every edit is a full rebuild, so a system
that edits parts frequently will hitch. Recipe: CT-02.

---

## 4. Tag-driven selection: rules plus a default

Parts contribute tags — body style, animation style, armour set. A selection set
maps required tags to a mesh or an animation layer, with a fallback:

1. gather tags from all active parts;
2. walk the rules in order;
3. the first rule whose required tags are **all** present wins;
4. otherwise use the default.

This microscopic pattern — an array of (asset, required tags) plus a default,
first match wins — is about ten lines and is worth copying wholesale. It is the
same shape whether it selects a mesh, a physics asset or an animation layer.

### Its one sharp edge

**Priority is array order.** There are no weights and no specificity ranking, so
a broad rule placed above a narrow one silently shadows it, and the symptom is a
wrong mesh rather than an error. Document the ordering requirement next to the
array, and validate that no rule's tag set is a subset of an earlier rule's.
Recipe: CT-03.

### Do not let cosmetic tags become gameplay tags

They may share a type. They must not share authority. A tag contributed by a
cosmetic part is client-realizable data; nothing that decides gameplay may read
it without an explicit, reviewed promotion.

---

## 5. Cosmetic lifecycle tests

Add and remove one part; several owners contributing; controller changes pawn;
pawn destroyed before controller cleanup; replicated add, remove and change; late
join reconstructs everything; **dedicated server spawns zero presentation
actors**; listen server does not realize twice; invalid part class logs rather
than crashes; incomplete tag set falls back.

---

# Part II — Teams

## 6. One authoritative source, and loud mirrors

Put the team identifier on the player state: it survives respawn, already
replicates, and belongs to player identity rather than to a body.

Controllers, pawns and local players may mirror it. The rules that make mirroring
safe:

- mirrors **subscribe** to the source and re-subscribe when the source object
  changes;
- a write to a mirror is **rejected loudly**, not silently ignored;
- a pawn may hold its own value only while unpossessed, and must say so in the
  error when it refuses.

The second rule is the one teams get wrong. A silent no-op setter on a mirror is
indistinguishable from a working setter until something depends on it. Log an
error naming the real owner. Recipe: CT-06.

---

## 7. Resolve team from an arbitrary object, in one place

Centralize the cascade so damage, UI, AI and targeting cannot each grow their own
version:

1. the object implements the team interface;
2. a pawn resolves through its controller or player state;
3. an actor resolves through its **instigator** — this is what lets projectiles
   and effects carry the shooter's team without owning one;
4. otherwise unassigned.

### Return a relationship, not a boolean

```text
same team / different teams / indeterminate
```

A boolean conflates "enemy" with "unknown", and the caller then has to guess.
Every caller must handle the third case explicitly — and "indeterminate means
allowed" is the failure that ships. See `ue-multiplayer-authority` for why an
error path that permits is worse than one that denies.

---

## 8. One damage policy, used by both authority and prediction

One function answers "may this instigator damage this target". The damage
calculation multiplies by its result as a scalar rather than branching, so the
team rule participates in the formula like any other modifier.

**The same function decides whether to show a hit marker.** That single choice
removes the entire class of "the client showed a hit and the server dealt no
damage" bugs, because there is no second implementation to disagree with.

### Make the policy configurable before you need it

Friendly fire, self-damage, damage to unassigned actors and per-mode overrides
are policy inputs. If they are hard-coded inside the damage calculation, a mode
that wants different rules requires editing the calculation.

Watch for the shape where a header comment promises settings that the body does
not implement — the comment is a design that was not built, and it reads as a
feature. Recipe: CT-07.

---

## 9. Presentation as a named parameter bag

A team display asset should hold **named material parameters** — scalars,
colours, textures, a short name — rather than a set of assets. Consumers ask for
a parameter; materials are authored to expect the names. Adding a team then costs
one asset instead of a duplicated material tree.

Apply it to meshes, effects and UI. Applying to an actor should include child
actors by default — that is precisely what carries team colour onto cosmetic
parts, and it is the only place the two halves of this skill touch.

### Two traps in the applying code

**Colour conversion drops alpha.** Converting a linear colour to a three-element
vector to feed a material parameter silently discards the fourth channel. If any
team parameter encodes opacity, it is gone. Recipe: CT-09.

**A viewer-relative parameter that is ignored.** If the API accepts a viewer
identity — "always show my own team as blue" — then the implementation must use
it. An accepted-and-ignored parameter is worse than an absent one: it makes the
feature look supported and unimplementable at the same time. Recipe: CT-10.

---

## 10. Replicate intent, realize locally — the shared principle

| Domain | Replicated intent | Local realization |
|---|---|---|
| cosmetics | part definitions | spawned components, meshes, materials |
| teams | team identifier | colours, UI, effects, nameplates |
| composition | selected definition | activated plugins and actions |

Realization must be **idempotent**: applying the same intent twice produces one
result. This is what makes late join deterministic from compact state.

---

## 11. Validation checklist

### Cosmetics

- [ ] part class is presentation-only and valid for the body;
- [ ] socket exists, or a fallback is defined;
- [ ] collision disabled by default;
- [ ] handle and spawned component are non-replicated;
- [ ] dedicated server realizes nothing;
- [ ] every owner retains removal handles;
- [ ] possession transfer removes then applies, exactly once;
- [ ] rule ordering documented, fallback present, no shadowed rules;
- [ ] no gameplay decision reads a cosmetic tag.

### Teams

- [ ] one authoritative source, authority-only writes;
- [ ] mirrors subscribe, re-subscribe, and refuse writes loudly;
- [ ] resolution is centralized and includes the instigator step;
- [ ] the indeterminate relationship is handled explicitly at every caller;
- [ ] damage and hit feedback call the same policy function;
- [ ] friendly fire and self-damage are configurable and tested;
- [ ] "private" team data is actually filtered, or is renamed;
- [ ] display parameters exist in the target materials;
- [ ] a viewer-relative API uses the viewer.

---

## 12. Keep them separate

They meet at one seam:

```text
team identifier → display asset → material parameters on cosmetic parts
```

Do not let cosmetics own the team identifier, and do not let the team system own
part selection. Separation is what allows skins independent of teams, players
with cosmetics and no team, team recolour over any skin, and viewer-relative
presentation without touching authoritative state.

Combine them only inside a small presentation adapter — never in authority or
replication ownership.

---

## Provenance

The findings behind the failure modes come from a source audit of Epic's Lyra
Starter Game on Unreal Engine 5.6 — roughly 1300 lines of cosmetics and 1800 of
teams, read rather than run. Several of the wiring call sites live in Blueprint
graphs, which are binary and were not read; those are marked open rather than
concluded, and the skill is written so that none of its claims depend on them.

Source addresses stay in the research archive. Each entry carries a stable
identifier (`CT-01`, `CT-02`, …) resolving back to the audited location there.

## Evidence boundary

One project, one engine version, one workspace. The limits are specific and worth
repeating: the components are added to actors from data assets that were not
read, the team colour application has no C++ caller, and the animation-layer
selection is invoked from a Blueprint. Absence of a C++ caller is **not** absence
of a caller — see the failure modes for how to check properly before deleting
anything.
