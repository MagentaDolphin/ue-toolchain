---
name: ue-multiplayer-authority
description: >-
  Design and review the authority model of a networked Unreal Engine product:
  which side owns each fact, what is predicted versus replicated versus
  validated, where responsibility boundaries run between GameState, PlayerState,
  Controller, Pawn and components, RPC and validation discipline, hit
  registration and lag compensation, replication modes, relevancy and cost, and
  the cheat surface. Use when starting a multiplayer feature, porting
  single-player code to network, reviewing trust boundaries, or investigating
  desync, rubber-banding, "works in PIE but not on dedicated server", or
  suspected cheating.
---

# UE multiplayer authority

The invariant:

> Every fact in a networked game has exactly one owner. Authority is not a
> property of code that says `HasAuthority` — it is the guarantee that no other
> machine can produce that fact.

Measured patterns from a reference product: [patterns](references/patterns.md).
Twenty detection recipes for silent trust failures:
[failure modes](references/failure-modes.md).

Read the failure modes before adopting or reviewing a networked design. Each
entry names the mechanism, why it stays silent, why the obvious check misses it,
and a command you can run against your own tree.

Related skills: `ue-gas-architecture`, `ue-gameplay-messaging`,
`ue-modular-gameplay`, `ue-cosmetics-and-teams`, `ue-architecture-guardrails`.

Method, not architecture — how to check any claim in this bundle before repeating it: `ue-evidence-discipline`.

---

## 1. Start from one question

Before any code: **for each fact in the game, who is allowed to be wrong about
it?**

- If a client being wrong is a cosmetic glitch → the client may own it.
- If a client being wrong is an advantage → the server must own it, and must be
  able to produce the value independently.
- If a client being wrong is unrecoverable → the server must own it *and*
  persist it.

This question, answered per fact and written down, is the authority model.
Everything else in this document is enforcement of that table.

### The three states of a networked fact

| State | Meaning | Who can be wrong |
|---|---|---|
| **Predicted** | Client computes it immediately for responsiveness; server may overrule | Client, temporarily, visibly |
| **Replicated** | Server computes it, clients receive it | Nobody — clients only observe |
| **Validated** | Client proposes it, server independently verifies before accepting | Client may lie; server must detect |

**The third is the expensive one, and it is the one that is usually missing.**
"Replicated" is often mistaken for "validated": a value that travelled from the
client to the server and was then replicated back out to everyone is *client
authored*, no matter how authoritative it looks on arrival.

---

## 2. What actually enforces authority

Unreal offers several mechanisms that look similar and enforce very different
amounts. Know which is which before relying on one.

| Mechanism | Enforces | Does not enforce |
|---|---|---|
| `HasAuthority()` guard | that this code path runs on the server | anything about callers that skip the guard |
| `UFUNCTION(Server)` | routing to the server | that the arguments are truthful |
| `WithValidation` | that a `_Validate` function runs and can disconnect | anything, if `_Validate` returns `true` unconditionally |
| `BlueprintAuthorityOnly` | that **Blueprint** cannot call this | nothing at all for C++ callers |
| replicated property | one-way flow server → client | that the server computed the value itself |
| `GetLifetimeReplicatedProps` conditions | who receives it | who may change it |

### Rules

1. **A public mutator on a replicated fact must guard itself**, not rely on its
   callers. `if (!HasAuthority()) return;` at the top of the function, not at the
   call site — call sites multiply.
2. **`WithValidation` with an empty `_Validate` is worse than none**: it passes
   review as validation while enforcing nothing.
3. **`BlueprintAuthorityOnly` is a Blueprint editor affordance.** Never cite it as
   a security property.
4. **Write the guard even when the only current caller is the server.** The guard
   is documentation the compiler enforces; the caller list is not stable.

---

## 3. Responsibility boundaries by layer

Put each fact in exactly one place. The most common source of networked bugs is a
fact that lives in two.

| Layer | Exists on | Owns | Must not own |
|---|---|---|---|
| **GameMode** | server only | match rules, spawning, scoring decisions | anything a client must read |
| **GameState** | server + all clients | match-wide replicated facts: phase, timer, team scores | per-player secrets |
| **PlayerState** | server + all clients | per-player facts everyone may see: name, team, score, abilities | input, camera, UI state |
| **PlayerController** | server + owning client | input, camera, client-directed commands, UI ownership | facts other players need |
| **Pawn / Character** | server + all clients | embodiment: transform, movement, physical state | player identity, persistent progression |
| **Components** | follow their owner | one cohesive slice of the owner's facts | facts belonging to a different layer |

### Rules

1. **`GameMode` exists only on the server.** Any client code path referencing it
   is a bug that PIE will hide.
2. **Persistent player facts belong to `PlayerState`, not the Pawn.** Pawns die.
3. **Input and camera belong to the Controller.** A Pawn reading input directly
   cannot be possessed by AI or spectated.
4. **A component's authority is its owner's authority.** A component attached to a
   client-owned actor cannot be authoritative regardless of its internal guards.
5. **Simulated proxies have no controller.** Any logic gated on "has a controller"
   silently excludes them; any logic that assumes one will null-deref on them.

---

## 4. RPC discipline

### Choosing the direction

```text
Client -> Server      UFUNCTION(Server, Reliable/Unreliable, WithValidation)
Server -> owner       UFUNCTION(Client, ...)
Server -> everyone    UFUNCTION(NetMulticast, ...)
```

### Rules

1. **Every `Server` RPC carries `WithValidation` and a `_Validate` that actually
   checks.** Range, ownership, state legality, rate. An RPC without validation is
   a client-side API into your server.
2. **Reliable is a budget, not a default.** Reliable RPCs are ordered and queued;
   overflowing the queue disconnects the client. Anything cosmetic, frequent or
   idempotent should be unreliable.
3. **Never multicast what a replicated property already carries.** The property
   handles joiners and relevancy; a multicast does not.
4. **Multicasts do not reach late joiners or newly relevant clients.** Anything a
   late joiner must know is state, not an event.
5. **Validate on the server that the sender owns the thing it is acting on.**
   Routing to the server proves nothing about the *subject* of the call.
6. **Rate-limit anything a client can call in a loop.**

### Debug and cheat commands

Cheat entry points reachable from a client are the highest-value target in the
codebase. They must be compiled out of shipping builds — not merely hidden,
disabled by a flag, or guarded by UI. A `Server` RPC that executes an arbitrary
cheat string, present in a shipping binary, is a remote console.

---

## 5. Prediction

Prediction exists to hide latency, not to save server work. The server must still
compute everything it accepts.

### Safe to predict

- movement through the engine's own prediction (correction path already exists);
- animation, audio, VFX, camera;
- UI affordances (cooldown wheels, ammo counters) that a correction can restore;
- ability activation under a prediction key, where the server can reject.

### Never predict

- damage application;
- score, currency, progression;
- inventory grants;
- death and elimination;
- anything persisted.

### Rules

1. **Every predicted value needs a defined correction path** — what happens
   visually when the server disagrees. Undefined correction means the client
   keeps a wrong value forever.
2. **Prediction is a client-side optimisation of a server-side truth.** If the
   server cannot independently produce the value, the feature is not predicted,
   it is client-authoritative.
3. **A prediction key is not validation.** It reconciles ordering; it does not
   check whether the client was entitled to act.

---

## 6. Hit registration — the decision that shapes the whole product

This is where authority is usually lost, and it is a design decision that must be
made explicitly and early, because retrofitting is expensive.

There are three positions:

| Model | Server does | Cost | Cheat exposure |
|---|---|---|---|
| **Server-authoritative trace** | traces from its own state at the current tick | cheap | none, but shots feel like they miss under latency |
| **Lag-compensated rewind** | stores per-tick historical positions, rewinds to the client's timestamp, re-traces | expensive: memory, CPU, complexity | low; the standard for competitive shooters |
| **Client-reported hit** | accepts the client's hit result | free | total |

### Rules

1. **Choose consciously and write the choice down.** Most projects arrive at the
   third by default, because the first feels bad and the second is work.
2. **If you accept client-reported hits, know exactly what a malicious client
   gains** — typically arbitrary damage, arbitrary range, arbitrary target,
   arbitrary surface multipliers.
3. **The server cannot validate what it cannot reproduce.** Without stored
   historical positions there is nothing to validate a client's hit *against*,
   so bolting on "validation" later is not a patch, it is building the rewind
   subsystem.
4. **Sanity checks are not validation, but they are not worthless.** Maximum
   range, line-of-sight from the shooter's replicated position, fire-rate limits,
   team check, and "was the target ever near there recently" raise the cost of
   trivial cheats even without full rewind.
5. **Never let the client choose damage-modifying inputs.** The surface/material
   that multiplies damage, the distance used for falloff, and the trace origin
   must all come from server-known state, even in a client-reported-hit model.
   These are the cheapest things to move server-side and the most valuable.

### Recognising a stub

Watch for parameters threaded through many function signatures but never branched
on, and for booleans initialised to a constant with a `//@TODO`. These are the
attachment points of a rewind subsystem that was designed and never built. They
make the code *look* like it validates. Recipes: NA-06, NA-07 in the failure
modes.

---

## 7. Replication cost and relevancy

Authority decisions determine correctness; relevancy decisions determine whether
the product ships.

### Rules

1. **Pick an ability-system replication mode deliberately.** `Full` replicates all
   gameplay effects to all clients; `Mixed` replicates effects to the owner and
   tags/cues to everyone; `Minimal` replicates no effects to anyone.
   Player-controlled actors want `Mixed`; AI want `Minimal`.
2. **Net cull distance is a gameplay decision, not a performance knob.** Setting
   it beyond the map size disables relevancy culling entirely — every actor
   replicates to every client, which is correct for a small arena and fatal for a
   large map.
3. **Prefer replicated state over event spam.** State is idempotent, survives
   packet loss, and reaches late joiners.
4. **FastArraySerializer for collections that change incrementally**, with the
   `PreReplicatedRemove` / `PostReplicatedAdd` / `PostReplicatedChange` callbacks
   all implemented — an empty callback is a client-side desync with no symptom on
   the server.
5. **Replication graph before you need it, or never.** Enabling it late changes
   which actors clients see, and every relevancy assumption in gameplay code has
   to be re-verified. If it ships disabled, treat routing configuration as
   untested.
6. **Cosmetic state should not replicate.** Replicate intent (which skin, which
   team), realise presentation locally.

---

## 8. Lifecycle across the network

1. **Readiness is a state chain, not a timing assumption.** Actor spawned,
   controller assigned, PlayerState replicated, data initialised, gameplay ready —
   each an explicit state with explicit transitions.
2. **Client and server reach each state in a different order.** Any code that
   assumes an order will work for the listen-server host and fail for remote
   clients.
3. **A simulated proxy passes through the chain without ever acquiring a
   controller.** Gates must handle that case explicitly rather than by omission.
4. **Every dynamic addition needs its exact removal**: granted abilities, applied
   effects, registered listeners, spawned cues, added tag paths. Test the removal
   on both server and client, in the same session, more than once.
5. **Death is not destruction.** Define the full sequence — death started, effects
   removed, input released, cues cleaned, actor destroyed or respawned — and give
   each step one owner.

---

## 9. The cheat surface review

Enumerate, for the shipping build, every path a malicious client can reach:

```text
1. Every Server RPC              -> does _Validate independently verify?
2. Every RPC argument            -> is any of it trusted without recomputation?
3. Every cheat/debug entry point -> is it compiled out, not just disabled?
4. Every damage input            -> which come from the client?
5. Every fail-open error path    -> what does the code do when a check errors out?
6. Every client-side gate        -> is there a matching server-side one?
```

Item 5 deserves attention: a permission check that returns "allowed" when it
cannot determine the answer converts an unknown state into an exploit. Failure to
determine must deny.

---

## 10. Test matrix

**PIE is not a network test.** A listen-server host shares memory with its client;
half of the failure modes here cannot occur in it.

### Mandatory configurations

- dedicated server + two remote clients;
- one client with 150 ms latency and 2% packet loss;
- a client joining mid-match;
- a client disconnecting mid-action;
- an actor becoming relevant and then irrelevant.

### Per feature

- does it work for a remote client, not just the host?
- does a late joiner reach the correct state?
- what does a simulated proxy see?
- what happens if the client sends the RPC twice, out of order, or with absurd
  arguments?
- is the state correct after death and respawn, twice?

### Authority regression

- for each fact in the authority table, assert on the server that the client
  cannot change it — with a test client that tries.

---

## 11. Review checklist

- [ ] Every fact has a named owner in a written authority table.
- [ ] Each fact is classified predicted / replicated / validated.
- [ ] Public mutators of replicated state guard themselves.
- [ ] Every `Server` RPC has `WithValidation` with a real `_Validate`.
- [ ] No trust in client-supplied damage inputs: origin, distance, surface, target.
- [ ] Hit registration model is chosen and documented.
- [ ] Cheat entry points are compiled out of shipping.
- [ ] Error paths deny rather than allow.
- [ ] Replication mode and net cull distance chosen per class, not inherited.
- [ ] FastArray callbacks all implemented.
- [ ] Every addition has a verified removal.
- [ ] Feature tested on a dedicated server with a remote client under latency.
- [ ] `BlueprintAuthorityOnly` is not cited as enforcement anywhere.

---

## 12. When client authority is the right answer

Deliberate client authority is legitimate when:

- the fact is purely presentational;
- the game is cooperative or single-player-with-friends and the threat model is
  "no adversary";
- the cost of server validation exceeds the value of the protected fact;
- an anti-cheat layer outside the game handles the threat.

In every one of these cases, the decision is written down with its threat model.
The failure worth avoiding is not "we trusted the client" — it is **"we did not
know we trusted the client."**

That distinction is what this skill exists to preserve. A codebase can be an
excellent architectural reference and simultaneously an unsafe network reference;
those are separate axes, and copying the first without noticing the second is the
common accident.

---

## Provenance

The findings behind the failure modes come from a line-by-line source audit of
Epic's Lyra Starter Game on Unreal Engine 5.6, read rather than run. That project
is an outstanding architectural reference and a poor network-security reference;
those are independent axes, and the audit exists to keep them apart. Source
addresses stay in the research archive that produced this skill; what ships is the
detection recipe, because an address in someone else's tree is not something you
can act on and a recipe is.

Each entry carries a stable identifier (`NA-01`, `NA-02`, …) that resolves back to
the audited location in that archive. If you need the original address to settle a
dispute, it exists and can be produced.

## Evidence boundary

The measured material refers to one specific reference project on one engine
version in one workspace. It is evidence of failure modes, not a guarantee about
other engine versions or other samples. Several claims in it are explicitly marked
as unanswerable without a dedicated-server build, and they stay unanswered. Re-run
the recipes against your own tree before trusting any specific claim.
