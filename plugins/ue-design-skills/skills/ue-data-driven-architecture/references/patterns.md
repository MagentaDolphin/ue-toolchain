# Patterns: a measured data-driven layer

A worked example of the layering rules from `SKILL.md`, measured in one reference
product. Unlike most files in this bundle it was produced **through a live editor
session**, not by reading source — because the thing being measured is data, and
data lives in binary assets.

That method is the first lesson and it is not a technicality. Everything below
would have been invisible, or wrong, from a text search.

Markers: **[measured]** — read from live objects through the editor;
**[derived]** — conclusion from measured facts; **[open]** — not readable with
the tools available.

---

## 1. The census, and why the obvious census is wrong

| Container | Count **[measured]** | Visible to a data-asset query |
|---|---:|---|
| Native data-asset instances, 21 runtime classes | 84 | yes |
| Zero-node Blueprint classes used as definitions | 23 | **no** |
| **Total inspected definition objects** | **107** | |

The 23 break down as ten gameplay definitions, seven item definitions and six
equipment definitions **[measured]**. In other words: **every gameplay,
item and equipment definition in the project is in the container that a
data-asset query does not return.**

**[derived]** A census that asks "which data assets exist?" returns 84, is
internally consistent, and misses the layer that actually composes the game. This
is the single most portable warning in this file. Recipe: DD-01.

The same structure produced a second trap. A generic property dump over one of
those class defaults reported almost nothing, because inherited fields were not
enumerated **[measured]**. Reading the *named* fields from the schema returned
full configuration. **[derived]** An empty reflection result is evidence about the
reflection call, not about the object. Recipe: DD-02.

---

## 2. The layer split, as actually built

```text
playlist  (8 instances)         map + definition + session and menu metadata
   └─ gameplay definition (10)  plugins + archetype + action sets + delta
        ├─ action set (5)       reusable slice
        └─ archetype (6)        pawn class, capabilities, input, policy, camera
             ├─ capability package (12)
             ├─ input config (5)
             └─ policy matrix (1, nine rules)
```

Two properties of this split are worth copying.

**The playlist knows about maps and menus; the definition does not.** One mode
can run on several maps, one map can host several modes, and menu metadata never
enters the runtime composition **[measured]** — all eight playlists were verified
to carry map, definition, visibility, default flag and player count, and nothing
gameplay-facing.

**Reuse is a list, not a parent.** Two shooter modes differ only by a
mode-specific delta — a different capability package, different scoring and music
components, different score widgets — while sharing input, components and HUD as
action sets **[measured]**. Adding a mode is editing a list.

That is enforced rather than merely encouraged: validation **rejects a Blueprint
subclass of a Blueprint definition** and its error text names composition as the
alternative **[measured]**. A validator that says what to do instead is worth
several that only refuse. Recipe: DD-05.

---

## 3. Composition is dependency injection, spelled as data

37 inline actions across ten definitions and five action sets **[measured]**. The
shape of the most common one:

```text
(target actor class, component class, apply on client?, apply on server?)
```

One mode adds scoring on both roles, music on the client only, and bot spawning,
team setup and spawn rules on the server only — **without modifying the game state
class** **[measured]**. A second mode swaps three of those and keeps the rest.

**[derived]** This is the payoff of the whole architecture, and it is worth
stating plainly: the base classes contain no branch per mode, because the modes
are not known to them. The switch test from the skill is passed by construction.

The same mechanism carries UI: one action pushes a layout into a layer, another
registers eleven widgets into named slots **[measured]**. Mode-specific UI is two
more rows in a list.

---

## 4. Where the role boundary is declared

Soft references in the action data carry bundle annotations, so the definition
declares composition **and** the cook boundary in one place **[measured]**.

The measured population is small and the number is instructive: **ten annotations
in the entire project — two for the client, eight for both roles** **[measured]**.

**[derived]** That is not a criticism; most content is loaded by other means. It
is a statement about how narrow the annotated surface is, which matters because
the consumers of those references use a bare accessor that returns null when the
bundle did not deliver, and one of the two loops checks the result while its
neighbour does not **[measured]**. The annotation and the null check are the two
halves of one contract, and only one half is consistently present. Recipes:
DD-03, DD-04.

---

## 5. The capability layer, and why input is not one-to-one with it

12 capability packages **[measured]**, ranging from an eleven-capability hero
package down to packages that grant **only effects** and no capabilities at all.

The instructive detail: **not every granted capability has an input tag**
**[measured]**. Death, spawn effects, auto-reload and auto-respawn are activated
by events and policies, not by a button.

**[derived]** This is the concrete reason to keep the semantic input layer
separate from the capability layer rather than folding one into the other. A
design that assumes "capability implies binding" has no place to put the four
above, and will grow a special case for each.

Six archetypes reuse the same capability packages across different pawn classes
and input configurations **[measured]** — one archetype reuses the shooter
capability package while changing pawn class and input config, which demonstrates
that implementation and capability are genuinely independent axes.

One archetype has a **null** pawn class **[measured]**. **[derived]** It is a
sentinel used as a configuration fallback, not an archetype — worth recognising
because a validator that requires a non-null class must special-case it, and a
validator that does not will be silently satisfied by every broken archetype.

---

## 6. Fragments: composition inside a definition

Item definitions carry a display name and a list of instanced polymorphic
fragments; consumers query by fragment class **[measured]**. The measured pipeline:

```text
pickup presentation (data asset)
└─ item definition (zero-node class)
   ├─ display, quickbar, pickup, reticle fragments
   ├─ ammo statistics
   └─ equippable fragment → equipment definition (zero-node class)
      ├─ runtime instance class
      ├─ capability package
      └─ actor to spawn, at a named socket
```

Three weapons differ only in these values **[measured]** — different instance
class, capability package, spawned visual, reticle fragment and ammo numbers —
with no change to the inventory or equipment managers.

**[derived]** The fragment list is what keeps the item definition from growing a
boolean and five fields for every item type that will ever exist. It is the same
move as the action list one layer up, applied inside a single asset.

---

## 7. The two content defects, and what they teach

**A health pickup that references the pistol item definition.** Two of them
**[measured]**. Both assets are valid, correctly typed and non-null; the graph is
intact and says something untrue.

**[derived]** No type check can catch this, and no validation in the project does.
The only mechanism that would is a weak semantic check — does a pickup's identity
share anything with the item it presents? — which feels too crude to write until
you see what it catches. Recipe: DD-07.

**Prototype content in the production tree.** One pickup carries a display name
and visual assets belonging to a different weapon entirely **[measured]**.

**[derived]** Prototype content in a production root is what makes the crude check
above hard to write, because naming stops being a signal. The two defects
compound: keep prototypes out of production roots and a naming heuristic becomes
viable.

Both are recorded here for the reason the whole bundle exists: **these shipped in
a reference project that many teams copy from.** Copying the architecture is
correct; copying the content is not.

---

## 8. Fields that exist and are never set

All eight playlists carry extra launch arguments and a replay flag. In every one
of the eight, the arguments are empty and the flag is false **[measured]**.

**[open]** Whether anything reads them cannot be settled from source, because a
consumer could be in a Blueprint graph. Recorded as open rather than concluded —
which is the honest form of this answer and the same discipline as any empty
search result.

**[derived]** Regardless of wiring, a field that is empty in every instance is an
extension surface rather than a feature, and a reader who assumes otherwise will
look for behaviour that is not there. Recipe: DD-08.

---

## 9. Validation: present, well built, and mostly not in the pipeline

| Fact **[measured]** | Reading |
|---|---|
| 12 validation entry points across the definition families | The discipline exists and is applied broadly |
| **11 of them compiled out of non-editor builds** | Feedback for authors, not a gate on the build |
| A content-validation commandlet and a validator base class exist | The mechanism to run them in automation is present |

**[derived]** This is the correct default arrangement, and it means the whole
question reduces to one that source cannot answer: does the build pipeline invoke
the commandlet, and does it fail on error? A validator whose result is printed
rather than returned is a log line.

Worth being precise about, because an earlier form of this material overstated
it: **structural validation exists in this project.** What does not exist is
semantic cross-family validation — nothing checks that a pickup presents the item
it claims to. The correct criticism is narrow, and the broad version ("the data
graph has no compiler") is wrong. Recipes: DD-09, DD-10.

---

## 10. What to copy, and in what order

1. **Separate the launch catalog from the runtime definition.** One asset type,
   large payoff, no dependencies on anything else here.
2. **Reusable slices as flat lists, and reject definition inheritance in
   validation** with a message naming the alternative.
3. **Fragments for optional facets**, so item definitions do not grow a field per
   item type.
4. **Bundle annotations beside soft references**, plus a null check at every
   consumer — the two halves of one contract.
5. **A cross-family semantic check**, however crude, run in automation with a
   non-zero exit status.

Items 1–3 are architecture and transfer directly. Items 4–5 are the parts the
audited reference left incomplete, and are therefore the parts most likely to be
inherited by anyone copying it.

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6 through a live
editor bridge on a single day: 84 native data assets across 21 runtime classes,
23 zero-node definition classes, 37 inline actions, all eight playlists, six
archetypes, twelve capability packages and five input configurations, read as
live objects and class defaults. No binary asset was parsed from disk; no
gameplay session was run.

Asset paths and configured values stay in the research archive that produced this
skill. Each `DD-` identifier resolves back to the audited location there.

## Evidence boundary

Graph assets — environment queries, state trees, blackboards — were enumerated
but their internals were **not** read, because no safe reader was available.
They are listed as present and nothing is claimed about their contents.

Everything here describes one project at one moment through one tool. Counts are
quoted to show the shape of a contrast, not as targets. Re-run the census against
your own project, and count both containers.
