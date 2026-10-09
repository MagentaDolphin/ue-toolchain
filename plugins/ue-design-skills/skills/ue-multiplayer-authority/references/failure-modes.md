# Failure modes: multiplayer authority

Twenty ways a networked Unreal project loses authority without anything going
wrong on screen. Each entry names the mechanism, why it stays silent, why the
obvious check misses it, the symptom, a recipe you can run against your own tree,
and the guardrail.

Two properties recur across this list and are worth stating once, because they
explain why these survive review:

- **PIE cannot reproduce most of them.** A listen-server host shares memory with
  its client, so the client/server split that produces the bug does not exist
  during the test that would have caught it. Entries NA-01, NA-04, NA-11, NA-13,
  NA-17 and NA-19 are invisible in PIE by construction.
- **Several of them look correct in review.** A `WithValidation` marker, a
  `BlueprintAuthorityOnly` specifier, a `bIsSimulated` parameter threaded through
  signatures — each reads as evidence of a server-side path that is not there.
  The specifier is real; the enforcement is not.

Recipes below use `rg`. They are written to be run from the root of a project's
source tree and to be read as a *comparison of two numbers*, not as a single
search: the whole class of defect here is "the thing is present, and the thing
that would make it mean something is absent".

---

## Trust boundaries

### NA-01 - Replicated is mistaken for validated

**Mechanism.** A value travels client to server and is then replicated back out to
everyone. On arrival it lives in an authoritative-looking replicated property, and
every later reader treats it as a server fact.

**Why it is silent.** Replication works perfectly. The value is consistent on every
machine, arrives in order, survives relevancy changes and late joins. Consistency
is not authorship, but consistency is what everyone observes and tests.

**Why the obvious check misses it.** Review asks "is this replicated?" and the
answer is yes. There is no compiler concept, specifier or naming convention that
distinguishes a server-computed replicated value from a server-relayed one. Both
compile to the same declaration.

**Symptom.** Nothing at all, until someone modifies a client. Then the value is
whatever that client chose, and it is authoritative across the whole session.

**Detect.** This one is a table, not a grep. List every replicated property and
name, for each, the server-side computation that produced it:

```bash
rg -n "UPROPERTY\([^)]*Replicated" Source/ | wc -l    # facts to account for
rg -n "GetLifetimeReplicatedProps" Source/            # where they are declared
```

For each result, answer in writing: *what did the server compute to get this?* If
the answer is "the client sent it", the fact is client-authored. A property whose
only writer is an RPC handler that assigns the parameter directly is the shape to
look for.

**Guardrail.** Classify every fact as predicted / replicated / validated in a
written table before the feature is built. "Validated" requires the server to
independently reproduce the value, not merely to receive it.

---

### NA-02 - `WithValidation` with an empty `_Validate`

**Mechanism.** The RPC carries the `WithValidation` specifier and the paired
`_Validate` function exists, so the engine calls it. Its body returns `true`
unconditionally.

**Why it is silent.** The mechanism is fully wired and working. The engine really
does call the validator and really would disconnect a client that failed it. There
is simply no input it rejects, and a validator that accepts everything is
indistinguishable at runtime from one that has nothing to reject yet.

**Why the obvious check misses it.** The specifier is what reviewers grep for, and
it is present. Declarations and implementations live in different files, so a
header review — the natural place to audit an RPC surface — never sees the body.

**Symptom.** The RPC accepts anything. Review signs off on the subsystem as
validated, and the estimate for "add validation" is later scoped as a patch when
it is a design.

**Detect.** Read every validator body, not the declarations:

```bash
rg -n --stats "WithValidation" Source/                       # declared validators
rg -n -A3 "_Validate\(" Source/ | rg -B1 "^\s*return true;"  # bodies that accept all
```

Compare the counts. On the measured reference the second command returned two
sites, both belonging to cheat RPCs. Any validator whose body is a bare
`return true;` is an unimplemented validator regardless of the specifier.

**Guardrail.** Require every `_Validate` body to check range, ownership, state
legality and rate. Treat a one-line `return true;` in a validator as a review
blocker, the same way an empty `catch` block is.

---

### NA-03 - `BlueprintAuthorityOnly` cited as enforcement

**Mechanism.** A function is marked `BlueprintAuthorityOnly`. The specifier stops
Blueprint graphs from calling it on a non-authoritative actor. C++ callers are
entirely unaffected.

**Why it is silent.** In a project where the function is only ever called from
Blueprint, the specifier does exactly what everyone believes it does. The gap
opens the first time a C++ caller appears, and that caller works, so nothing draws
attention to it.

**Why the obvious check misses it.** The word "authority" is in the specifier.
Grepping for authority-related terms finds it and it looks like a guard. It is an
editor affordance whose name describes intent rather than enforcement.

**Symptom.** A function documented and reviewed as authority-guarded is reachable
from any C++ path, including client code, and mutates replicated state from there.

**Detect.** Enumerate the sites and check each for a real guard in the body:

```bash
rg -n "BlueprintAuthorityOnly" Source/                  # claimed guards
rg -n -A6 "BlueprintAuthorityOnly" Source/ \
  | rg "HasAuthority|GetLocalRole"                      # actual guards
```

A large gap between the two counts is the finding. On the measured reference the
specifier appeared at five sites across three subsystems, with no `HasAuthority`
in the guarded bodies.

**Guardrail.** Never cite `BlueprintAuthorityOnly` as a security property in a
review, a comment or a design document. Add an explicit `HasAuthority()` guard
inside the function body; keep the specifier only as an editor hint.

---

### NA-04 - Guard placed at the call site rather than in the mutator

**Mechanism.** A public mutator of replicated state relies on its callers to check
authority. Today every caller does.

**Why it is silent.** The invariant holds for as long as the caller list is what it
was when the code was written. Nothing degrades gradually; the code is correct
until one day it is not, and the transition is a new caller, not an edit to the
function.

**Why the obvious check misses it.** Reading the function shows nothing wrong —
there is no missing line, because the check was never meant to be there. Reading
the call sites shows a check at each one. Both halves pass review independently.
The defect only exists in the relationship between them, which no single file
review inspects.

**Symptom.** Works until a new caller appears — commonly a subclass in a feature
plugin, a Blueprint node, or a second caller added by someone who reasonably
assumed the mutator guards itself. Then a client writes replicated state directly.

**Detect.** Find public or virtual writers of replicated state whose own body has
no guard:

```bash
# 1. names of replicated properties
rg -n -o "UPROPERTY\([^)]*Replicated[^)]*\)\s*\n\s*\w+\s+(\w+)" -r '$1' Source/
# 2. for each name, find assignments and check the enclosing function
rg -n -B12 "\bDeathState\s*=" Source/ | rg "HasAuthority|void |virtual"
```

Substitute your own property name in step 2. The finding is an assignment whose
preceding function signature is public or virtual and whose body contains no
authority check.

**Guardrail.** `if (!HasAuthority()) return;` as the first line of the mutator.
Write it even when the only current caller is the server: the guard is
documentation the compiler enforces, and the caller list is not a stable property.

---

### NA-05 - Client-supplied damage inputs

**Mechanism.** Distance, trace origin, surface material or target identity arrive
in the RPC payload and feed the damage calculation directly.

**Why it is silent.** Every value is in a plausible range, because a normal client
sends plausible values. The damage numbers that result look exactly like correct
damage numbers. There is no error state and no log line, because nothing failed.

**Why the obvious check misses it.** The damage code is usually reviewed for
correctness of the formula, and the formula is correct. The question that matters
is not "does this compute the right number?" but "who chose the inputs?", and the
inputs arrive as ordinary function parameters several layers away from where they
entered the process.

**Symptom.** Arbitrary damage multipliers from a modified client, invisible in
logs. In a competitive game this surfaces as player reports that a specific
weapon or surface "feels wrong", long before anyone suspects the trust boundary.

**Detect.** Trace each damage-modifying input back to its origin:

```bash
rg -n "PhysicalMaterial|PhysMat|TraceStart|HitLocation|Distance" \
  Source/ --glob "*Damage*" --glob "*Execution*"
```

For each hit, answer: did the server compute this, or did it arrive from the
client? On the measured reference the falloff distance and the surface multiplier
both came from client-supplied fields, while the team check beside them was
genuinely server-side — the model was incomplete, not absent, which is the harder
case to spot.

**Guardrail.** Recompute every damage-modifying input from server-known state. The
shooter's replicated position and a server-side collision query cover most of it
and are cheap. Client-supplied values may inform presentation, never arithmetic
that changes an outcome.

---

### NA-06 - Validation flag initialised to a constant

**Mechanism.** A boolean local is initialised to a literal — `const bool bIsValid
= true;` — and then consumed by branches that read as validation. There is no
computation between the initialisation and the use.

**Why it is silent.** A permanently-valid result is a legal runtime state. Every
branch takes the path it would take on a successful validation, which is also the
path taken during all normal play, so the code behaves exactly as intended for
every non-malicious input.

**Why the obvious check misses it.** The flag has a meaningful name, appears in
conditionals, and is used more than once. Any search for "is validation present?"
finds a variable called `bIsTargetDataValid` being consumed by a gate and stops
there. The tell is the *initialiser*, which is three lines above and looks like
boilerplate.

**Symptom.** The code path reads as validated in review and in estimates. Nothing
is observable at runtime until a modified client sends implausible data and it is
accepted.

**Detect.** Look for boolean locals initialised to a literal and later consumed as
gates, restricted to network-relevant code:

```bash
rg -n "const bool b\w+\s*=\s*(true|false)\s*;" Source/
```

Then, for each hit, check whether the name promises a computation
(`bIsValid`, `bCanApply`, `bIsAuthorized`) and whether the variable is read by a
branch. On the measured reference this returned eight sites; most were legitimate
call-parameter constants, and exactly one — a target-data validity flag inside a
weapon ability — was a validation stub. The recipe's value is that it reduces the
whole codebase to a list short enough to read.

**Guardrail.** Treat any boolean local in a network path whose initialiser is a
literal and whose name asserts a property as unimplemented until proven otherwise.
If validation is not written yet, name the variable for what it is.

---

### NA-07 - Dead parameters that imply a server path

**Mechanism.** A parameter such as `bIsSimulated` is threaded through many function
signatures, passed a literal at the only call site, and never branched on
anywhere.

**Why it is silent.** The parameter is passed and received correctly at every
level. Nothing is unused in the compiler's view, so no warning fires. The code
does what it does today with complete consistency.

**Why the obvious check misses it.** Signature review is exactly the wrong
instrument here, and it is the instrument reviewers reach for when auditing a
subsystem's shape. A parameter appearing in ten signatures is strong evidence to a
human that a feature exists. Confirming it requires following the value to a
branch, which no IDE affordance does for you.

**Symptom.** A reviewer concludes a simulated or authoritative path exists.
Estimates for "just add server validation" come out an order of magnitude low,
because the attachment points were mistaken for the subsystem.

**Detect.** Count mentions, then count branches:

```bash
P='bIsSimulated'
rg -n "\b$P\b" Source/ | wc -l                          # mentions: many
rg -n "if\s*\(\s*!?\s*$P\b|\?\s*.*:\s*.*\b$P\b" Source/ # branches: ?
```

On the measured reference the parameter appeared at ten sites and was branched on
at zero. A high first number with an empty second is a mounting point, not a
feature.

**Guardrail.** Trace every network-relevant parameter to a branch. No branch means
no feature: either implement it or delete the parameter, because its presence is
an active lie to the next reader.

---

### NA-08 - Retrofitting hit validation without rewind

**Mechanism.** The server holds no historical positions, so there is nothing to
validate a timestamped client hit against. Validation is scheduled as a task on
top of the existing weapon code.

**Why it is silent.** The absence is an absence. Nothing in the codebase points at
the missing subsystem; there is no stub, no TODO, no failing test. The weapon
system works, feels good, and passes playtests, because every client is honest
during a playtest.

**Why the obvious check misses it.** The question "do we validate hits?" gets
answered by looking at the hit path, which is full of plausible machinery. The
right question is one level down and is about a subsystem nobody expects to find
by reading weapon code: does the server store per-tick positions at all?

**Symptom.** "Add server validation" is scoped as a patch and turns out to be a
subsystem. Partial attempts produce shots that visibly miss under latency, which
is then treated as a regression and reverted.

**Detect.** Ask whether the machinery exists at all, before reading any weapon
code:

```bash
rg -n "FSavedMove|ServerMove|CompressedFlags|SavedMoves|PositionHistory" Source/
```

Empty output means there is no lag compensation and no custom movement
prediction, and therefore no basis for hit validation in principle. On the
measured reference this returned nothing at all, which explains every other
finding in this file about client trust: they are consequences of one absent
subsystem, not independent oversights.

**Guardrail.** Decide the hit-registration model — server trace, lag-compensated
rewind, or client-reported — before the weapon system exists, and record the
decision with its threat model. Interim sanity checks (max range, line of sight
from the replicated position, fire rate, team) raise cheat cost without full
rewind and are worth having in every model.

---

### NA-09 - Fail-open permission check

**Mechanism.** A check returns "allowed" on an indeterminate or error result. The
error branch was written to avoid blocking legitimate play during development.

**Why it is silent.** The indeterminate case does not arise in normal play. Both
participants are always fully initialised, always have a PlayerState, always have
a resolved team. The permissive branch is dead code for the entire duration of
every test.

**Why the obvious check misses it.** The function has a check, the check is
correct in the determinate cases, and unit tests cover those cases. Reviewing the
error branch requires asking "what if this returns the error value?", and the
answer during development is "it doesn't".

**Symptom.** Rules bypassed exactly in the edge cases nobody tested — early
initialisation, missing PlayerState, a disconnecting client, an actor spawned
before its owner. For a friendly-fire check this means damage applied where team
rules should have prevented it.

**Detect.** Find the error branches of permission checks and read their return
value:

```bash
rg -n -B3 -A3 "InvalidArgument|Indeterminate|Unknown" Source/ \
  | rg "return true|return .*Allow|bCanDamage\s*=\s*true"
rg -n "//\s*@?TODO.*temporar" -i Source/
```

The second command is worth running on its own: a permissive branch marked
temporary is the highest-confidence instance of this class.

**Guardrail.** Failure to determine must deny. Make the error branch explicit and
restrictive, and if a permissive default is genuinely needed during development,
gate it on a build configuration so it cannot ship.

---

### NA-10 - Cheat RPC surface in shipping

**Mechanism.** `Server` RPCs taking arbitrary command strings are declared outside
any build-configuration guard. The implementation may be neutralised; the surface
is not.

**Why it is silent.** The commands are useful, work as intended, and are reached
through a UI that only appears in development. Hiding the entry point in the UI
feels like removing it, and the difference never shows up in play.

**Why the obvious check misses it.** The guard that reviewers look for is usually
present *somewhere* — around the cheat manager, around the console UI, around the
implementation body. Confirming the RPC declaration itself is unguarded means
checking a header for the absence of a preprocessor directive, which is not
something a code search naturally expresses.

**Symptom.** A remote console in the shipped binary. Any client that can encode
the RPC can execute arbitrary cheat strings on the server.

**Detect.** Check whether the declarations sit inside a build guard:

```bash
rg -n "UFUNCTION\([^)]*Server[^)]*\)" -A2 Source/ | rg -i "cheat|exec|command"
rg -n -B8 "void Server(Cheat|Exec)" Source/ | rg "#if|UE_BUILD_SHIPPING"
```

An empty second result with a non-empty first is the finding. Note the
distinction the recipe forces: whether the *implementation* is neutralised in a
shipping configuration is a separate question that only a packaged build answers,
and it should stay marked as open until someone answers it.

**Guardrail.** Wrap declaration *and* implementation in `#if !UE_BUILD_SHIPPING`
or an equivalent cheat-manager guard. Hiding the UI is not removal.

---

## Replication shape

### NA-11 - Multicast used where state belongs

**Mechanism.** A one-shot multicast conveys a fact that a late joiner needs. It
reaches everyone connected and relevant at the moment it fires.

**Why it is silent.** For everyone present, it works. The fact arrives, the visual
plays, the state is right. The failure is scoped precisely to players who were not
there, and those players see a plausible world — just the wrong one.

**Why the obvious check misses it.** Testing is done by players who join before
the match starts, which is the configuration in which the bug cannot occur.
Joining mid-match is a separate deliberate test that has to be designed.

**Symptom.** Players who join, or become relevant, after the event see the wrong
state permanently. It never self-corrects, because nothing re-sends an event.

**Detect.** Enumerate multicasts and ask what each one carries:

```bash
rg -n "UFUNCTION\([^)]*NetMulticast" -A3 Source/
```

For each, answer: if a player joined one second after this fired, what would they
see? Then run the test — join mid-round and inspect the state of every feature.
This is a runtime check by nature; the grep only produces the list to test.

**Guardrail.** Anything a late joiner must know is replicated state. Multicasts
carry transient presentation only — a sound, an impact, a one-frame effect whose
absence is invisible a second later.

---

### NA-12 - Reliable RPC overflow

**Mechanism.** Frequent or per-frame reliable RPCs fill the reliable queue.

**Why it is silent.** The queue is generous. At two players on a local network it
never fills. The cost scales with player count, latency and packet loss
simultaneously, so it stays invisible across the entire range of configurations
used during development.

**Why the obvious check misses it.** Each individual call site is defensible —
one reliable RPC is nothing. The failure is a sum over call sites and time, and no
review reads all of them together.

**Symptom.** Clients disconnect under load, typically first observed in a
playtest at full player count, and usually attributed to the network rather than
to a specific call site.

**Detect.** Count reliable RPCs and look for the ones a client can trigger
repeatedly:

```bash
rg -n "UFUNCTION\([^)]*\bReliable\b" Source/ | wc -l
rg -n "UFUNCTION\([^)]*\bReliable\b" -A3 Source/ \
  | rg -i "tick|update|move|aim|look|input|cosmetic"
```

The second command finds reliable calls on names that imply frequency. Confirm
with a load test at maximum player count and 2% packet loss, watching for
queue-overflow disconnects.

**Guardrail.** Reliable is a budget, not a default. Cosmetic, frequent or
idempotent calls are unreliable; rate-limit anything a client can call in a loop.

---

### NA-13 - Incomplete FastArray callbacks

**Mechanism.** `PreReplicatedRemove`, `PostReplicatedAdd` and
`PostReplicatedChange` are partially implemented. A derived cache or local
listener list is updated in some of them and not others.

**Why it is silent.** The server is always right, because the server never runs
the callbacks that are missing — it mutates the array directly. Only clients
apply deltas, so only clients drift, and they drift into a state that is
internally consistent.

**Why the obvious check misses it.** All three callbacks exist as overrides, so a
structural review finds a complete-looking implementation. The empty one has a
valid signature and compiles. Server-side tests pass because the defect cannot
exist on the server.

**Symptom.** Client-side desync with no symptom on the server — the hardest class
of bug to attribute, because every server-side log and dump shows correct state.

**Detect.** Compare the three callbacks per FastArray type:

```bash
rg -n "FFastArraySerializer" -l Source/ | while read -r f; do
  echo "== $f"
  rg -n -A4 "Pre(ReplicatedRemove)|Post(ReplicatedAdd|ReplicatedChange)" "$f"
done
```

Read the bodies. An empty body next to two implemented ones is the finding.
On the measured reference one replicated structure had an empty removal hook and
no callers at all — harmless while unused, a silent desync the moment it is
adopted, which is the worst possible time to discover it.

**Guardrail.** Implement all three or none. Assert cache/array consistency in
development builds so the drift becomes an error rather than a mystery.

---

### NA-14 - Relevancy disabled by an inherited constant

**Mechanism.** A net cull distance chosen for a small arena is inherited by a
large map. Beyond the map's own size, the setting disables relevancy culling
entirely.

**Why it is silent.** It is not a bug on the map it was chosen for — it is the
correct setting there, and it makes gameplay better. The value carries forward
because it is in a base class, and base-class defaults are not re-examined when a
new map is added.

**Why the obvious check misses it.** The number is a squared distance, which
makes it unreadable at a glance: nine hundred million does not announce itself as
three hundred metres. Reviewers see a tuned-looking constant and move on.

**Symptom.** Bandwidth and server CPU scale with total actor count instead of
local density. Discovered at player-count scale-up, late, when the fix requires
re-verifying every gameplay assumption about who can see whom.

**Detect.** Find the value and convert it:

```bash
rg -n "SetNetCullDistanceSquared|NetCullDistanceSquared\s*=" Source/ Config/
```

Take the square root of each result and compare it to the largest map's diagonal.
On the measured reference the value corresponded to a 300 m radius on arena maps —
correct there, fatal if inherited into an open world.

**Guardrail.** Treat net cull distance as a per-class gameplay decision with a
stated map-size assumption written next to it, not as an inherited performance
knob.

---

### NA-15 - Replication graph enabled late

**Mechanism.** The graph implementation and its routing configuration exist, and
the graph ships disabled. The routing is therefore never exercised.

**Why it is silent.** Disabled means the default replication path runs, and the
default path is correct. The configuration file looks maintained. Nothing
degrades, because nothing is using it.

**Why the obvious check misses it.** The presence of a configured routing table is
read as evidence that the feature is in use. Confirming otherwise means finding
the one boolean that disables the whole thing, which lives in a settings class
rather than next to the routing.

**Symptom.** Enabling it changes which actors clients see, breaking gameplay code
that had silently assumed universal relevancy. The breakage appears far from the
change, in features nobody associated with replication.

**Detect.** Check the enable flag before trusting the routing:

```bash
rg -n "bDisableReplicationGraph|bEnableReplicationGraph" Source/ Config/
rg -n "ClassNodeMapping|RepGraph" Config/
```

A disabled flag beside a populated routing table means the routing is untested
configuration, not working configuration.

**Guardrail.** Enable it early or treat it as unavailable. Re-verify every
relevancy assumption at the moment it is turned on, and treat that as a project
milestone rather than a settings change.

---

### NA-16 - Wrong ability-system replication mode for AI

**Mechanism.** `Mixed` is inherited for AI-controlled actors. `Mixed` replicates
gameplay effects to the owning client — and an AI has no owning client to
receive them.

**Why it is silent.** It is correct for player-controlled actors, which is where
it was chosen, and it is not wrong for AI either — merely wasteful. Waste has no
symptom until bandwidth is the constraint.

**Why the obvious check misses it.** All three modes are one-line calls in
constructors spread across different classes. There is no place where the choice
is expressed as a policy, so nobody reviews the set of choices together.

**Symptom.** Bandwidth spent replicating gameplay effects nobody reads. Shows up
as an unexplained baseline in profiling, attributed to player count.

**Detect.** List every mode choice in one place:

```bash
rg -n "SetReplicationMode|EGameplayEffectReplicationMode::" Source/ \
  | sed 's/.*EGameplayEffectReplicationMode:://' | sort | uniq -c
```

On the measured reference all three ability-system components used `Mixed`, with
`Minimal` and `Full` absent from the module entirely — a default applied
uniformly rather than a decision made three times.

**Guardrail.** `Mixed` for player-controlled, `Minimal` for AI, `Full` only with a
written reason. Put the three choices in one comment block so they are reviewed
as a policy.

---

## Lifecycle

### NA-17 - Readiness gate that assumes a controller

**Mechanism.** An initialisation chain waits for a controller. Simulated proxies
on remote clients never receive one.

**Why it is silent.** The host is fine. The listen-server's own pawn has a
controller, and so does every pawn in a single-process test. The stall happens
only on machines that are not running the authority, which is the configuration
least often exercised.

**Why the obvious check misses it.** The gate reads as obviously correct — of
course initialisation waits for the controller. The missing knowledge is not in
the code, it is that simulated proxies exist and never satisfy the condition. A
reviewer who knows that spots it instantly; one who does not cannot find it by
reading more carefully.

**Symptom.** Remote clients see uninitialised characters forever. Reproduces only
with a dedicated server, so it is often first reported by QA and not reproducible
by the developer.

**Detect.** Find readiness conditions that mention a controller:

```bash
rg -n -B4 -A4 "GetController\(\)|Controller\s*!=\s*nullptr|IsPlayerControlled" \
  Source/ --glob "*Init*" --glob "*Extension*" --glob "*Ready*"
```

For each, ask what a simulated proxy does at that line. The measured reference
handles this correctly — its init-state gate permits progression without a
controller — and is worth reading precisely because the naive version of the same
gate deadlocks every simulated proxy while working perfectly in PIE.

**Guardrail.** An explicit named state chain, with the no-controller case handled
deliberately rather than by omission. Write down which states a simulated proxy
reaches.

---

### NA-18 - Addition without verified removal

**Mechanism.** Granted abilities, applied effects, registered listeners and
spawned cues accumulate across death/respawn or feature activation cycles,
because the addition path was built and the removal path was assumed.

**Why it is silent.** One cycle is fine. Two cycles produce a duplicate, and a
duplicate of an idempotent-looking effect is usually invisible. The cost grows
linearly with session length, and development sessions are short.

**Why the obvious check misses it.** Both halves exist in most cases — there is a
removal function, it is called, and it removes *something*. Whether it removes
exactly what was added requires holding the handle, and a review that sees
`Remove` next to `Add` reasonably concludes the pair is complete.

**Symptom.** Duplicated effects after the second respawn; leaks that only appear
in long sessions; a second feature activation that adds a second copy of every
widget.

**Detect.** Compare addition and removal sites per resource type, then test:

```bash
rg -n "GiveAbility|ApplyGameplayEffect|AddLoadedGameplayCuePath|RegisterListener" \
  Source/ | wc -l
rg -n "ClearAbility|RemoveActiveGameplayEffect|RemoveLoadedGameplayCuePath|Unregister" \
  Source/ | wc -l
```

Unequal counts are a starting point, not a verdict. The verdict is runtime:
baseline, activate, deactivate, compare to baseline, reactivate — on both server
and client, twice in one session.

**Guardrail.** Every dynamic addition retains an ownership handle and an exact
rollback, tested on both server and client, twice in one session. Assert on the
removal count where the API returns one.

---

### NA-19 - Prediction without a correction path

**Mechanism.** A client-predicted value has no defined behaviour when the server
disagrees. The prediction key reconciles ordering; nothing reconciles the value.

**Why it is silent.** The server rarely disagrees on a local network with an
honest client. Disagreement requires latency, packet loss or a rejected action,
and the development environment supplies none of them.

**Why the obvious check misses it.** The prediction machinery is present and
correct, and prediction keys are a real feature that really works. Reviewing
"is this predicted properly?" finds a correct implementation of prediction. The
missing piece is a design question — what does the player see when we were
wrong? — that has no code location to be missing from.

**Symptom.** The client keeps a wrong value indefinitely. UI and gameplay diverge
with no error anywhere, and the player's experience is that the game lied to them
once and never corrected.

**Detect.** Force disagreement and watch:

```bash
rg -n "ScopedPredictionWindow|PredictionKey|GetPredictionKeyForNewAction" Source/
```

For each predicted value, run the paid test: introduce 150 ms latency, make the
server reject the action, and observe the client for ten seconds. A value that
does not converge has no correction path. This one cannot be settled statically.

**Guardrail.** Define, per predicted value, what the correction looks like to the
player. A prediction key reconciles ordering, not entitlement.

---

### NA-20 - PIE treated as a network test

**Mechanism.** The listen-server host shares memory with its client, so the
serialisation, ordering and relevancy boundaries that produce networked defects do
not exist during the test.

**Why it is silent.** PIE multiplayer looks like multiplayer. Two windows, two
players, two views of one world. Everything that works there works convincingly,
including the things that only work because the boundary is absent.

**Why the obvious check misses it.** The check *is* the test, and the test passes.
There is no artefact to inspect and no code to review; the defect is in the
choice of configuration, which is made once, early, by whoever set up the
workflow, and never revisited.

**Symptom.** Features ship having never run in the configuration they will run in.
Entries NA-01, NA-04, NA-11, NA-13, NA-17 and NA-19 above cannot occur in PIE at
all.

**Detect.** Audit the test configuration rather than the code:

```bash
rg -n "PlayNetMode|RunUnderOneProcess|bLaunchSeparateServer" Config/ Saved/Config/
```

If the editor is configured for a listen server in one process, no networked
feature in the project has been tested. Confirm by running one known-networked
feature under a dedicated server with a remote client and comparing behaviour.

**Guardrail.** Dedicated server plus two remote clients, one with 150 ms latency
and 2% packet loss, as the minimum configuration for accepting a networked
feature — including a mid-match joiner.
