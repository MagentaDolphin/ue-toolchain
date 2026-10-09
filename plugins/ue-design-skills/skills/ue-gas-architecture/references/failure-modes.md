# Failure modes: GAS architecture

Fourteen ways a Gameplay Ability System layer misbehaves without reporting
anything.

The shared property, stated once: **GAS failures present as absence.** An ability
that does not activate, a phase query that answers false, a grant that is never
revoked, a cost that is never charged. The framework is built to tolerate a
refused activation, because a refused activation is a normal gameplay state. So
the diagnostic burden is entirely yours, and the useful question is never "did it
error" but "which side of the seam owns this fact".

Each entry gives the mechanism, why it stays silent, why the obvious check misses
it, the symptom a human reports, a `Detect` recipe, and the guardrail.
Identifiers (`GA-01` and up) are stable and resolve back to the audited source in
the research archive.

Recipes use `rg` and run from a project's source root. They were executed against
the audited project while this file was written.

---

## Ownership and receipts

### GA-01 - Grant with no receipt, permanent by omission

**Mechanism.** An ability set is granted with the out-parameter for handles left
null. The grant then lasts as long as the ability system component.

**Why it is silent.** Permanent is a legitimate lifetime, and the API is designed
to offer it. Nothing distinguishes "permanent because we decided" from "permanent
because the argument was easy to omit".

**Why the obvious check misses it.** The call is correct, the API is used as
documented, and the reviewer sees a grant that works. The defect only exists
relative to an intention that lives in nobody's head at review time.

**Symptom.** A capability that should have been removed with the feature, the
equipment or the round survives it. Usually noticed after a respawn, when the
player has two of something.

**Detect.** List every grant site and classify it by whether it keeps a receipt:

```bash
rg -n -B3 "GiveToAbilitySystem" --glob "*.cpp" .
```

Any call passing `nullptr` for the handles parameter is a permanent grant. In the
audited project this is exactly one site — the pawn baseline on the player state —
and the equipment path beside it passes a receipt stored in its applied-item
entry. One permanent grant with a stated reason is a design; several are a leak.

**Guardrail.** Make permanence explicit at the call site, in a comment naming the
lifetime the grant is tied to. Review new grant sites against the table of
allowed permanent grants rather than against the API signature.

---

### GA-02 - Revocation that removes more than it granted

**Mechanism.** Teardown clears abilities by class, by tag, or by clearing all
abilities on the component, instead of by the handles the grant returned.

**Why it is silent.** The abilities the caller wanted removed *are* removed. The
extra removals affect capabilities another owner granted, and that owner is not
watching.

**Why the obvious check misses it.** The teardown function looks thorough. "Remove
everything matching this class" reads as more robust than "remove these three
handles", not less.

**Symptom.** Unequipping one item removes an ability granted by a different
feature. Reproduces only when two owners granted overlapping capabilities, which
is rare in a test and common in a shipped game.

**Detect.** Find removals that are not keyed on stored handles:

```bash
rg -n "ClearAbility\(|ClearAllAbilities|RemoveActiveGameplayEffect" --glob "*.cpp" . -B5 \
  | rg -n "(GetAssetTags|StaticClass|ForEach|\.Class)"
```

Removal keyed on anything other than a handle produced by the matching grant is
the finding.

**Guardrail.** Every revoke path takes a receipt and removes exactly its contents.
If a receipt was not kept, the correct fix is to keep one, not to widen the
removal.

---

### GA-03 - Grant order that applies effects before their attributes exist

**Mechanism.** An ability set grants effects before it grants attribute sets, so
an effect modifies an attribute that has not been added yet.

**Why it is silent.** Applying a modifier to a missing attribute is not an error
in the framework — the modifier simply finds nothing to modify. The effect is
applied, the handle is valid, the log is clean.

**Why the obvious check misses it.** Each block of the grant function is correct
in isolation, and the whole function reads as a straightforward three-part loop.
Order dependencies between the parts are invisible unless you know the effects
reference the attributes.

**Symptom.** An attribute sits at its default value despite an effect that should
have initialized it. Investigated as a bad effect asset.

**Detect.** Read the grant function and confirm the sequence:

```bash
rg -n -A40 "::GiveToAbilitySystem" --glob "*.cpp" . \
  | rg -n "(AddAttributeSetSubobject|GiveAbility|ApplyGameplayEffect)"
```

The line numbers must run attributes, then abilities, then effects. The audited
implementation gets this right and the ordering is worth copying verbatim.

**Guardrail.** State the order as a comment in the grant function, and add a test
that grants a set whose effect initializes an attribute the same set provides.

---

## State that lies

### GA-04 - Server-only subsystem queried from clients

**Mechanism.** Phase abilities are configured server-only, and the subsystem that
tracks them is created on every client anyway. Its map of active phases is
therefore always empty on a client, and the "is this phase active" query always
returns false there.

**Why it is silent.** False is a valid answer to that question. The client is not
told that it asked a question it cannot answer; it is told "no".

**Why the obvious check misses it.** The subsystem exists on the client, is
correctly initialized, and answers immediately. Every structural check passes.
The creation gate that would have prevented it exists too — commented out, with
the unconditional `return true` left in place. Reading that function tells you
someone thought about it, not what they concluded.

**Symptom.** Client-side UI that reacts to match phase never reacts. Blamed on
replication, on the widget, on the tag — rarely on the query itself.

**Detect.** Find subsystem creation gates that were considered and abandoned:

```bash
rg -n -A12 "ShouldCreateSubsystem" --glob "*.cpp" . | rg -n "^\s*//.*(return|check|World)"
```

Then, for every server-authoritative subsystem, check whether any client code
path queries its state:

```bash
rg -n "IsPhaseActive|IsRoundActive|GetCurrentPhase" --glob "*.cpp" .
```

**Guardrail.** A subsystem whose state is authority-only either refuses to be
created without authority, or its queries return a tri-state that distinguishes
"no" from "I cannot know". Clients observe phase through replicated tags,
replicated state or messages — never through the authoritative tracker.

---

### GA-05 - Observer registration with no handle

**Mechanism.** A subscription API appends a callback to an array and returns
nothing. There is no way to unsubscribe.

**Why it is silent.** Subscriptions work. The list grows, and a growing list has
no symptom until it is large or until a captured object needed to die.

**Why the obvious check misses it.** The API is complete from the caller's
perspective: subscribe, get called back. The missing half is a function that does
not exist, and reviews do not notice absent functions.

**Symptom.** Callbacks firing on objects that logically ended, and a list that
grows until the world resets. In the audited project the authors documented this
themselves, in two consecutive comments above the function, and shipped it —
including the honest second thought that a handle would not help if callers
ignored it.

**Detect.** Find subscription functions that return void:

```bash
rg -n "void \w+::When\w+|void \w+::(Register|Subscribe|Observe)\w*\(" --glob "*.cpp" .
```

Any registration whose return type is void is a subscription that cannot be
undone.

**Guardrail.** Registration returns a handle; the handle unregisters. If callers
cannot be trusted to hold handles, bind weakly *and* sweep expired entries — but
the sweep is an addition to the handle, not a substitute for it.

---

### GA-06 - Write-only field

**Mechanism.** A member is declared and assigned in the constructor, and read
nowhere.

**Why it is silent.** It is a correctly initialized member of a working class. It
costs nothing at runtime and breaks nothing.

**Why the obvious check misses it.** Searching for the name finds two hits — a
declaration and an assignment — which reads as "declared and used". An
unused-variable warning does not fire, because the write *is* a use.

**Symptom.** No runtime symptom. The cost is comprehension: the field's name
promises behaviour, and a future engineer will implement against a flag that
nothing consumes. In the audited project the field is a cancellation-logging flag
whose own comment describes it as temporary, added while tracking a bug that has
since closed.

**Detect.** Compare writes against reads for suspicious members:

```bash
F='bLogCancelation'
rg -n "\b$F\b" --glob "*.h" --glob "*.cpp" .
```

Two hits — declaration and assignment — with no comparison, no branch and no
pass-by-value is the finding. This is the mirror image of the missing-writer
check: here the writer exists and the reader does not.

**Guardrail.** Delete it. A flag with no consumer is a comment that pretends to be
code, and it will eventually be believed.

---

## Performance and correctness on the activation path

### GA-07 - Function-static containers on a per-activation path

**Mechanism.** A function called during every ability activation declares
function-local `static` containers as scratch space to avoid reallocation.

**Why it is silent.** It is correct on a single thread, and every activation
happens on the game thread today. The reuse is invisible because each call clears
before use.

**Why the obvious check misses it.** The pattern looks like a deliberate
optimization, and it is one. Nothing at the call site says "this function is not
reentrant", and reentrancy through an ability that activates another ability is
plausible but not obvious.

**Symptom.** Nothing, until the function is called from a second thread or
reentrantly — at which point tag requirements are computed from another call's
scratch data and an ability activates when it should not.

**Detect.** Find statics in functions on the activation path:

```bash
rg -n "static F\w+Container|static TArray" --glob "*.cpp" . -B10 \
  | rg -n "(CanActivate|SatisfyTagRequirements|ActivateAbility)"
```

The audited project has three such statics in one activation-path function.

**Guardrail.** Use a member scratch buffer on an instanced object, or accept the
allocation. If the static stays, document the single-thread and
non-reentrancy assumption at the declaration, where the next reader will see it.

---

### GA-08 - Linear scan marked provisional, on the hot path

**Mechanism.** A relationship or lookup table is walked linearly on every
activation, with a comment acknowledging that a real index would be needed at
scale.

**Why it is silent.** It is correct at every size. Only the cost changes, and cost
does not report itself.

**Why the obvious check misses it.** The comment is the check, and it is
addressed to a future that has not arrived. Reviewers read "for now" as "someone
is tracking this".

**Symptom.** Activation cost grows with the size of a designer-authored data
asset, discovered during a late-project profiling pass when the table has grown
by two orders of magnitude.

**Detect.** Find provisional comments on lookup paths:

```bash
rg -n "Simple iteration|for now|O\(n\)|linear" --glob "*.cpp" . -A4 \
  | rg -n "(for\s*\(|ForEach)"
```

In the audited project the same provisional comment appears three times in one
mapping class, and the mapping is consulted on every activation and on every
block-and-cancel application.

**Guardrail.** Record the size at which the structure must change, and add an
assertion or a test that fails when the data crosses it. "For now" without a
number never ends.

---

## Attributes and damage

### GA-09 - Meta attribute treated as durable state

**Mechanism.** An incoming-damage or incoming-healing attribute — designed as a
one-shot channel that converts to a health change and resets to zero — is read,
replicated or stored as if it held a value between executions.

**Why it is silent.** The attribute exists and always has a value. Reading it
outside an execution returns zero, which is a plausible number.

**Why the obvious check misses it.** Nothing in the type distinguishes a meta
attribute from a state attribute. The distinction lives in a comment and in the
post-execution code that zeroes it.

**Symptom.** UI or logic that reads "current damage" and always sees zero, or a
replicated attribute that costs bandwidth and carries nothing.

**Detect.** Confirm each meta attribute is zeroed after conversion and excluded
from replication:

```bash
rg -n "SetDamage\(0|SetHealing\(0" --glob "*.cpp" .
rg -n "DOREPLIFETIME.*\b(Damage|Healing)\b" --glob "*.cpp" .
```

A meta attribute that appears in the replication list, or one that is never
zeroed, is the finding.

**Guardrail.** Group meta attributes under an explicit comment banner in the
header, keep them out of the replication list, and mark state attributes that
executions alone may change so the editor enforces it rather than the team
remembering it.

---

### GA-10 - Out-of-health fired more than once for one death

**Mechanism.** The zero-health signal is emitted from a change handler that can
run several times as clamping, max-health changes and replication settle.

**Why it is silent.** Each individual emission is correct. Listeners are expected
to handle a broadcast; nothing says "at most once per life".

**Why the obvious check misses it.** The emitting code is a single line in a
single place. The multiplicity comes from how many paths reach it, which is
visible only by enumerating callers of the enclosing handler.

**Symptom.** Two death sequences, doubled elimination messages, score credited
twice. Often first noticed in the kill feed rather than in gameplay.

**Detect.** Find the emission and check for a latch:

```bash
rg -n -B12 "OnOutOfHealth.Broadcast" --glob "*.cpp" . | rg -n "bOutOfHealth|bAlready|if\s*\(!"
```

An emission with no guarding flag, or a flag that is never reset when health
recovers, is the finding. The audited implementation has both the latch and the
reset — copy that shape.

**Guardrail.** Latch the signal, reset the latch when the value recovers, and
assert in development that the death transition runs once per life.

---

### GA-11 - Placeholder attribute initialization

**Mechanism.** Attributes are initialized by assigning one to another in code —
health set to max health — with a comment saying a data-driven initialization
will replace it.

**Why it is silent.** The result is a live, plausible character. Nothing about a
full-health spawn looks provisional.

**Why the obvious check misses it.** The data-driven mechanism usually *exists*
alongside it — an initialization-data field on the grant structure, a curve table
setting — so a reviewer looking for "is initialization data-driven?" finds the
machinery and stops.

**Symptom.** Designer-authored initialization values have no effect, because the
code path that would consume them is bypassed by the placeholder.

**Detect.** Find initialization marked as temporary, then check whether the
data-driven path has any consumer:

```bash
rg -n "TEMP|placeholder|Eventually this will" --glob "*.cpp" . -A3 \
  | rg -n "(SetNumericAttributeBase|InitFromMetaDataTable|InitStats)"
rg -n "GlobalCurveTableName" Config/
```

In the audited project the placeholder is present, the global curve table is set
to none, and the initialization-data field on the grant structure has no traced
consumer.

**Guardrail.** A placeholder initialization is acceptable only with the
data-driven path deleted or disabled, so nobody can author data that silently
does nothing.

---

## Lifecycle

### GA-12 - Activation group counters that do not balance

**Mechanism.** A per-group active count is incremented on activation and
decremented on end. Any path that ends an ability without notifying the component
leaks a count.

**Why it is silent.** A leaked count does not error. It makes the group look
occupied, so later activations are refused — which is indistinguishable from
correct exclusivity.

**Why the obvious check misses it.** Both the increment and the decrement exist
and are correctly paired in the normal path. The leak comes from an abnormal end:
a destroyed avatar, a cancelled ability that refuses cancellation, an early return.

**Symptom.** After some sequence involving death or a cancelled ability, exclusive
abilities stop activating for that pawn. Restarting the match fixes it, which
makes it look like corruption rather than arithmetic.

**Detect.** Find increments and decrements and confirm they are in paired
notification hooks:

```bash
rg -n "ActivationGroupCounts" --glob "*.cpp" . -B4
```

Any mutation outside the activated/ended notification pair is a leak candidate.
Then assert the invariant directly: the exclusive counts must never exceed one in
total.

**Guardrail.** Assert the invariant in development builds at every mutation, and
test the abnormal ends explicitly — avatar destroyed mid-ability, cancel refused,
ability ended from a task callback.

---

### GA-13 - Death represented only as a health comparison

**Mechanism.** Consumers ask "is health at or below zero" instead of reading a
durable death state.

**Why it is silent.** The comparison is true at the right moments. It is also true
during the window before the death sequence starts, and true again if health is
restored and re-zeroed within one sequence.

**Why the obvious check misses it.** The comparison is simple, local and obviously
correct. The state machine it replaces lives in another component, and using it
requires knowing it exists.

**Symptom.** Systems that disagree about whether a character is dead, especially
across the network, and a predicted death that cannot be corrected because there
is no state to roll back.

**Detect.** Find health comparisons used as death tests:

```bash
rg -n "GetHealth\(\)\s*<=?\s*0|Health\s*<=\s*0\.?0?f?" --glob "*.cpp" .
```

Every hit outside the attribute set itself should be reading a death state
instead.

**Guardrail.** One replicated, monotonic death state with an explicit
start and finish, owned by a domain component, with the ability system supplying
only the numeric signal that triggers it.

---

### GA-14 - Failure reason discarded at the seam

**Mechanism.** Activation fails, the framework records a reason, and the project
does not forward it — or forwards it only on the server, where no UI exists.

**Why it is silent.** A refused activation is normal. The player sees nothing,
which is exactly what a refused activation looks like when the reason is missing.

**Why the obvious check misses it.** The failure path exists and is exercised
constantly. What is absent is the delivery of the reason to the machine that can
render it, and absence of delivery has no call site to review.

**Symptom.** The player presses a button and nothing happens, with no feedback
distinguishing "on cooldown" from "out of ammo" from "you are dead". Designers
compensate with generic click sounds.

**Detect.** Check that failure tags are both produced and delivered to the owning
client:

```bash
rg -n "OptionalRelevantTags|NotifyAbilityFailed|ActivateFail" --glob "*.cpp" . -A6 \
  | rg -n "(Client|Broadcast|Message)"
```

Failure tags produced with no client-notification path is the finding. The audited
project does this correctly: a client notification carries the tags, the ability
maps them to text and animation in data, and delivery goes over a message bus so
the UI never references GAS.

**Guardrail.** Every failure reason reaches the locally controlled player as a
tag, never as a log line, and the mapping from tag to feedback lives in data.
