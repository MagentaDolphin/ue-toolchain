# Patterns: authority in a measured reference product

A worked example of the authority model from `SKILL.md`, against one specific
reference project read as source. It is here for one reason: the failure modes in
[failure-modes.md](failure-modes.md) are easier to believe, and much easier to
apply, when you can see how they cluster in a real codebase.

**Read this first.** The project audited below is an outstanding architectural
reference and a poor network-security reference. Those are independent axes. None
of what follows is a criticism of the sample — a learning project that ships no
product has no reason to build lag compensation — but copying its structure
without noticing its trust boundaries is a real and common accident, and it is the
accident this skill exists to prevent.

Markers: **[measured]** — read in source; **[derived]** — conclusion from measured
facts; **[open]** — not answerable without a dedicated-server build, and left
open rather than guessed.

---

## 1. The headline: one absence explains almost everything

No custom saved-move type, no custom server-move path, no compressed-flags
extension, and no historical position storage anywhere in the project
**[measured]**.

Without stored per-tick positions the server has nothing to rewind to, and
therefore **cannot** validate a client's hit claim even in principle
**[derived]**. The client trust documented below is not carelessness at individual
call sites; it is the necessary consequence of a subsystem that was never built.

This is the single most valuable thing to carry away from the audit, and it
generalises: **before reading a weapon system, ask whether the machinery that
would make validation possible exists at all.** If it does not, every "missing
check" you find downstream is one symptom of one decision, not a list of
independent bugs. Recipe: NA-08.

Practical implication for anyone adopting such code: "add server validation to the
weapon system" is not a patch. It is building the rewind subsystem first.

---

## 2. Hit registration was client-authored end to end

Four findings, each of which reads as an isolated defect and is not:

| What was measured | Consequence |
|---|---|
| The targeting trace early-returns unless locally controlled — the server never traces **[measured]** | The client decides what was hit |
| A target-data validity flag is a `const bool` initialised to `true`, consumed twice, with no computation between **[measured]** | The code path reads as validated in review; NA-06 |
| Distance falloff is computed from a client-supplied trace origin; the damage multiplier is taken from a client-supplied surface material **[measured]** | A modified client controls falloff and multiplier directly **[derived]**; NA-05 |
| A `bIsSimulated` parameter appears at ten sites, is passed a literal at its single call site, and is branched on nowhere; a hit-replacement helper is never called **[measured]** | Attachment points for the rewind subsystem that was never built **[derived]**; NA-07 |

One check in that path was genuinely server-side: the team comparison guarding
whether damage may be caused at all **[measured]**. That detail matters more than
it looks. **The model was incomplete, not absent** — which is the harder case,
because the presence of one real server-side check makes the surrounding code read
as server-side too.

---

## 3. Three mechanisms that look equivalent and are not

One equipment component demonstrated all three in a single file **[measured]**:

| Declaration | Actually enforces |
|---|---|
| `UFUNCTION(Server, Reliable, BlueprintCallable)` | routing only — no `WithValidation` |
| `UFUNCTION(BlueprintAuthorityOnly, ...)` | blocks Blueprint callers; no effect on C++ |
| plain C++ writes elsewhere in the same class | nothing |

`BlueprintAuthorityOnly` is an editor affordance. It appears in review as an
authority guard and is not one **[derived]**. Across the whole project the
specifier appeared at five sites in three subsystems, none of which carried an
authority check in the guarded body **[measured]**. Recipe: NA-03.

Unguarded state transitions followed the same shape: the death-state writers were
public, virtual, and unguarded, with the only barrier being a server-initiated
activation policy on one ability **[measured]**. The guard belongs in the mutator,
not in one of its callers **[derived]** — the call-site list is not a stable
property, and virtual functions mean a subclass in a feature plugin inherits the
hole. Recipe: NA-04.

---

## 4. Cheat surface and error handling

Two arbitrary-string cheat RPCs were declared outside any build-configuration
guard **[measured]**. Their validators return `true` unconditionally
**[measured]** — which is defensible for a cheat RPC and is also exactly the shape
NA-02 looks for, so the recipe finds them first and you must read what you found.
Whether the implementations are neutralised in a shipping configuration is
**[open]** without a packaged build; the RPC surface itself is unconditional.

A team-comparison helper returned a permissive result on an invalid-argument
outcome, carrying a comment marking it temporary **[measured]**. Since that
function gates friendly fire, the failure mode is damage applied where team rules
should have prevented it **[derived]**.

Rule extracted, and it is worth more than the finding: **failure to determine must
deny.** Recipe: NA-09.

---

## 5. Replication configuration

| Setting | Measured | Reading |
|---|---|---|
| Ability-system replication mode | `Mixed` on all three ability-system components; `Minimal` and `Full` absent from the module **[measured]** | Correct for player-controlled actors; wasteful when inherited by AI **[derived]**; NA-16 |
| Net cull distance | A squared value corresponding to a 300 m radius, set in the character base class **[measured]** | Every character relevant to every client at all times **[derived]** — correct for a small arena, fatal if inherited into a large map; NA-14 |
| Replication graph | Ships disabled, with class routing configured **[measured]** | The routing is untested configuration, not working configuration **[derived]**; NA-15 |
| A replicated fast-array | Empty removal callback, no callers in the project **[measured]** | Harmless while unused; a silent client-side desync the moment it is adopted **[derived]**; NA-13 |

The last row is the one worth pausing on. An unused structure with an incomplete
callback set is invisible to every kind of testing, because nothing exercises it.
It becomes a defect at adoption time — the moment when the person adopting it has
the least context to recognise what they inherited.

---

## 6. What the reference got right

For balance, and because these are the parts worth copying directly:

1. **An explicit init-state chain** instead of timing assumptions. Its gate
   permits progression for actors without a controller, which is what allows
   simulated proxies to initialise at all **[measured]**. The naive version of the
   same gate deadlocks every simulated proxy on remote clients while working
   perfectly in PIE **[derived]** — study the correct one before writing your own.
   Context: NA-17.
2. **A replication mode chosen deliberately** for player ability-system components
   rather than left at the engine default **[measured]**.
3. **Replicate intent, realise presentation locally** — the cosmetic system sends
   which parts to wear, not the assembled result **[measured]**.
4. **Correct teardown where it exists**: one pawn-extension path checks avatar
   identity before cancelling abilities, clearing input and removing cues
   **[measured]**. Note the shape — identity check first, then reverse-order
   removal.
5. **The team check in the damage execution is genuinely server-side**
   **[measured]**. The model is not absent, it is incomplete.

---

## 7. Questions the audit could not answer

Left open deliberately. Each requires a dedicated-server or packaged build, which
was out of scope:

1. Whether the cheat RPC implementations are neutralised in a shipping
   configuration.
2. Actual bandwidth per client, and whether the relevancy radius holds at full
   player count.
3. Behaviour of the replication graph when enabled — routing completeness,
   dormancy usage.
4. Whether client and server tag registries match when feature plugins load
   asymmetrically.
5. Real reconciliation behaviour of ability prediction under packet loss.

An audit that answers questions it cannot answer is worth less than one that
enumerates them. If you adopt this material, these five are yours to close.

---

## Provenance

Measured against Epic's Lyra Starter Game on Unreal Engine 5.6, read as source in
a single workspace. Source addresses stay in the research archive that produced
this skill; each `NA-` identifier above resolves back to the audited location
there. Numbers without an author are worth less than no numbers, so: this is where
these came from, and they can be produced on request.

## Evidence boundary

Every claim above refers to one project on one engine version. These are examples
and failure evidence, not guarantees about other engine versions or other samples.
Verify version-sensitive claims against your target engine before acting on them.
In particular: PIE cannot reproduce most of the failure modes described here,
because a listen-server host shares memory with its client.
