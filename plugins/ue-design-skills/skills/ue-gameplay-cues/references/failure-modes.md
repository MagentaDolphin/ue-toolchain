# Failure modes: GameplayCues

Twenty ways a cue-based presentation layer fails without saying so.

The shared property of this list, stated once so it is not repeated twenty times:
**a cue defect is silent by construction.** The mechanism is a tag join with no
validation, delivering an event that is *allowed* to be missed, to a layer that
does not exist on the server. Every diagnostic has to be built deliberately,
because the engine will not volunteer one.

Each entry gives the mechanism, why it stays silent, why the obvious check misses
it, the symptom a human reports, a `Detect` recipe you can run against your own
tree, and the guardrail. Identifiers (`GC-01` and up) are stable and resolve back
to the audited source in the research archive.

Detection recipes use `rg` (ripgrep). They were run against the audited project
while this file was written; where a first-draft recipe gave a wrong answer, the
corrected form is the one printed here and the trap is called out.

---

### GC-01 - Gameplay logic inside a notify

**Mechanism.** Damage, scoring, state changes or spawning placed in a cue notify,
because the notify is where the designer was already working.

**Why it is silent.** In the editor and on a listen server the notify runs on the
same process that owns gameplay, so the write lands and the feature appears
correct. Nothing anywhere declares that a notify is presentation-only.

**Why the obvious check misses it.** Code review of the notify reads as reasonable
gameplay code, and it *is* reasonable — in the wrong file. The defect is not in the
statement, it is in the file the statement is in. No compiler, linter or test that
runs in-editor can see it.

**Symptom.** The feature works for everyone during development and simply does not
happen on a dedicated server. Reported as "the server build is broken".

**Detect.** Look for writes inside notify classes:

```bash
rg -n --type cpp -g '*Cue*' \
  "(ApplyGameplayEffect|AddScore|->Server|SpawnActor|SetHealth|=\s*true;)" \
  Source/
```

Stronger, and the one that actually settles it: run the feature on a dedicated
server with every cue asset removed. Gameplay results must be identical.

**Guardrail.** A notify may read state and produce audiovisual output, nothing
else. Review every notify for writes, and keep the dedicated-server-without-cues
run in the acceptance list for any feature that ships a cue.

---

### GC-02 - Cue tag with no notify asset

**Mechanism.** An effect references a cue tag; no notify is registered for it —
a typo, an unscanned directory, or a plugin that failed to register its path.

**Why it is silent.** An unhandled cue is a legal runtime state: the engine
delivers the event to a registry that has no entry, and returns. Missing
presentation is exactly what "presentation is optional" means, so there is nothing
for the engine to complain about.

**Why the obvious check misses it.** The tag exists, the effect compiles, the asset
cooks. Both halves of the join are individually valid; only their *relation* is
broken, and nothing in the toolchain owns that relation.

**Symptom.** Silence. No visual, no log, no error. The artist is told the effect
"doesn't work" and starts editing a notify that was never being called.

**Detect.** Compare the two sides of the join. Tags referenced by content versus
tags claimed by notifies:

```bash
rg -no "GameplayCue\.[A-Za-z0-9_.]+" Content/ Source/ | sort -u
```

Feed both sets into a diff. Then prove your tooling works by deliberately
misspelling one cue tag and confirming the check reports it — a validator nobody
has seen fail is not known to work.

**Guardrail.** Constrain cue tag properties with `meta=(Categories="GameplayCue")`
so authoring uses a dropdown; add a content validator that resolves every
referenced tag against the runtime index; log once per unhandled cue in
development builds.

---

### GC-03 - Notify asset that no tag references

**Mechanism.** The reverse orphan: a notify exists for a tag nobody fires,
usually left behind by a rename or a cancelled feature.

**Why it is silent.** An unreferenced notify is still scanned, indexed and
sometimes preloaded. It behaves exactly like a notify waiting for its first
trigger, which is a normal state.

**Why the obvious check misses it.** Reference-viewer style checks ask "what does
this asset reference?", not "who addresses this asset by string?" Nothing
references a notify by hard pointer — that is the entire point of the design.

**Symptom.** No symptom at all, which is why it accumulates. It surfaces as
unexplained package count and memory in the cue set.

**Detect.** Same recipe as GC-02, read in the other direction: tags claimed by
notify assets minus tags referenced by effects. Run the validator both ways in one
pass, and report both orphan directions separately.

**Guardrail.** One validator, two directions, in CI. Orphan notifies are deleted
in the same commit that finds them, or the list stops being read.

---

### GC-04 - Per-instance state on a Static notify

**Mechanism.** A Static notify runs on the class default object. A member written
during one invocation persists into every later invocation, including other
players'.

**Why it is silent.** Single-player and single-source testing never overlaps two
invocations, so the shared member always holds the value the current caller just
wrote. The bug requires concurrency to appear.

**Why the obvious check misses it.** The class looks like an ordinary object with
ordinary members. Nothing at the declaration site says "this is a singleton" — the
CDO behaviour comes from how the cue manager dispatches, which is in a different
file entirely.

**Symptom.** One player's cue reads another player's data. Effects that are correct
alone and wrong in multiplayer, intermittently.

**Detect.** Find mutable members on Static notify classes:

```bash
rg -n -A40 "class .*GameplayCueNotify_Static" Source/ \
  | rg -n "^\s*(float|int32|bool|F[A-Z]\w+|T\w+<)[^()]*;"
```

Any non-const, non-config member on a Static notify is the defect.

**Guardrail.** Static notifies hold no mutable state. If state is needed, it is an
Actor notify — that is what the distinction is for.

---

### GC-05 - Looping cue that is never removed

**Mechanism.** `OnActive`/`WhileActive` spawns a persistent effect; `OnRemove`
does not destroy it, or never runs because the owning effect was removed by a path
that skipped cue removal.

**Why it is silent.** A spawned particle system is a legitimate long-lived object.
Nothing distinguishes "still playing because the effect is active" from "still
playing because nobody stopped it".

**Why the obvious check misses it.** The first death-respawn cycle usually looks
clean, because the leak needs a second cycle to become visible as duplication.
Most manual testing stops at one cycle.

**Symptom.** Accumulating VFX and audio across respawns; frame time degrading over
a match; a bug report that says "it gets worse the longer you play".

**Detect.** For each duration-form notify, check that the removal path destroys
what the activation path spawned:

```bash
rg -n "OnActive|WhileActive|OnRemove" Source/ -g '*Cue*' -A15 \
  | rg -n "(SpawnSystem|SpawnEmitter|SpawnSound|Destroy|Deactivate)"
```

Then count active cue actors before and after two full death-respawn cycles. The
count must return to baseline, not merely stop growing.

**Guardrail.** Everything the duration forms spawn, `OnRemove` destroys. Write
`OnRemove` to be safe when `OnActive` never ran on that client.

---

### GC-06 - `OnActive` without `WhileActive`

**Mechanism.** Start-of-loop logic placed only in `OnActive`, which fires only for
clients present at the moment the effect began.

**Why it is silent.** For every client who was present, the behaviour is perfect.
The failure exists only in the experience of a client who was not, and that client
sees an absence — the hardest thing to notice.

**Why the obvious check misses it.** Both callbacks exist on the class, so a
structural review ticks the box. The difference between them is a delivery-timing
property of the engine, not a property of the code you are reading.

**Symptom.** Players who join, or who lose and regain relevancy, see nothing while
everyone else sees the effect. Reproduces only with a real client join, never in a
single-process test.

**Detect.** Find notifies that implement one callback and not the other:

```bash
rg -l "OnActive" Source/ -g '*Cue*' > /tmp/active.txt
rg -l "WhileActive" Source/ -g '*Cue*' > /tmp/while.txt
comm -23 <(sort /tmp/active.txt) <(sort /tmp/while.txt)
```

Anything listed implements the start and not the catch-up.

**Guardrail.** `OnActive` and `WhileActive` must converge on the same visual state.
Test by joining a match mid-effect, and by losing and regaining relevancy during a
loop.

---

### GC-07 - Two addressing routes for one tag

**Mechanism.** The same cue tag is fired both by a gameplay effect and by a direct
ability-system call, or additionally handled through the cue interface on the
actor.

**Why it is silent.** Each route is individually correct and each was added by
someone solving a real problem. The duplication is a property of the pair, which
no single author sees.

**Why the obvious check misses it.** Searching for the tag finds both sites, but
they look like they belong to different features — one in an effect asset, one in
C++. Nothing marks a cue tag as having an owner.

**Symptom.** Doubled effects, appearing only when both paths trigger, often only in
one game mode. Reported as "the explosion is twice as loud in Team Deathmatch".

**Detect.** For each cue tag, enumerate every firing route:

```bash
TAG="GameplayCue.Fire.Impact"
rg -n "$TAG" Source/ Content/ Config/
rg -n "(ExecuteGameplayCue|AddGameplayCue|RemoveGameplayCue)" Source/ -A2 | rg -n "$TAG"
```

More than one owner is the defect, even when the current behaviour looks right.

**Guardrail.** One owner per cue tag, documented at the tag declaration. Search
every route before adding a firing site.

---

### GC-08 - Manual cue added without a manual removal

**Mechanism.** A direct add call has no effect behind it, so no effect removal will
ever clean it up.

**Why it is silent.** The add succeeds and the presentation appears. Removal is a
separate call that nobody is forced to write, and the object model does not record
that a removal is owed.

**Why the obvious check misses it.** The code that adds is present and correct. The
defect is the absence of a second call on every exit path, and absence is what
review is worst at seeing.

**Symptom.** A looping cue that survives the state that created it — including
across death, possession change and disconnect.

**Detect.** Count adds against removes:

```bash
rg -c "AddGameplayCue" Source/
rg -c "RemoveGameplayCue" Source/
```

An imbalance is a lead, not a verdict — then check each add site for a paired
removal on *every* exit path, not just the happy one.

**Guardrail.** Direct-call cues need an explicit paired removal on every exit path.
Prefer attaching the cue to an effect's lifetime instead, so removal is structural
rather than remembered.

---

### GC-09 - Teardown without an avatar identity check

**Mechanism.** A component unbinds an ability system component unconditionally,
without checking that the ASC's current avatar is still this actor.

**Why it is silent.** The unbind succeeds. The damage is done to a *different*
actor's state — the one the ASC has already moved to — so the error surfaces far
from its cause.

**Why the obvious check misses it.** The teardown code is correct in isolation and
correct in the common case. It is wrong only in the ordering where the avatar
changed first, which single-process testing rarely produces.

**Symptom.** Abilities and cues on the *current* avatar are cancelled when an old
one is cleaned up. Looks like a spontaneous ability cancellation with no cause.

**Detect.** Find unbind paths and check for an identity guard above them:

```bash
rg -n -B8 "(ClearAbilityInput|CancelAbilities|RemoveAllGameplayCues|SetAvatarActor\(nullptr)" Source/ \
  | rg -n "GetAvatarActor\(\)\s*==|IsValid\(.*Avatar"
```

An unbind path with no `GetAvatarActor()` comparison above it is the defect.

**Guardrail.** Verify the ASC's avatar is this actor before cancelling abilities,
clearing input and removing cues. The audited project does this correctly; the
guard is one comparison and it is worth copying verbatim.

---

### GC-10 - Cue assets in the server bundle

**Mechanism.** Cue content is assigned to an asset bundle that the dedicated
server loads.

**Why it is silent.** Loading extra assets is never an error. The server runs
correctly, just fatter, and nothing reports "you loaded a particle system you can
never play".

**Why the obvious check misses it.** Bundle assignment lives in asset manager
configuration, not next to the cue content. Reviewing the cue does not show you
which bundle it is in.

**Symptom.** Server memory spent on particles and audio. Discovered, if ever,
during a memory investigation months later.

**Detect.** Find where cue paths are registered and which bundle constant is used:

```bash
rg -n "AddGameplayCueNotifyPath|GameplayCueRefs|LoadState" Source/ -B3 -A3
```

The bundle name at that site should be the client bundle. Cross-check against
the asset manager's bundle definitions.

**Guardrail.** Cue paths belong to the client bundle only. Make the bundle constant
explicit at the registration site so review can see it without opening
configuration.

---

### GC-11 - Load policy that short-circuits the whole subsystem

**Mechanism.** A load-mode constant causes an early return at every switch site,
including the one that binds the subsystem's delegates.

**Why it is silent.** Every branch is a legal configuration. "Load everything
upfront" is a sensible mode; the fact that choosing it disables an entire preload
subsystem is an emergent property of three separate switch statements, none of
which says so.

**Why the obvious check misses it.** The preload machinery exists, is maintained,
and is full of correct code. Reading it tells you nothing about whether it runs.
Worse, the diagnostic command built for it reports **zero**, which reads as "there
is nothing to preload" rather than "this code never executes".

**Symptom.** A named feature that has no effect. Engineers investigate the preload
implementation for a bug that is not in it.

**Detect.** Find the mode constant, then find every switch on it, then check which
branch each falls into:

```bash
rg -n "static .*LoadMode\s*=" Source/
rg -n "switch\s*\(.*LoadMode" Source/ -A12
```

If the configured value hits an early `return` at a site that also performs
delegate binding, everything below that binding is unreachable. In the audited
project three switch sites short-circuit, and the third returns before its
delegate bindings.

**Guardrail.** Verify the load policy reaches its intended branch. Treat "the dump
command shows nothing" as a question about reachability, not about content.

---

### GC-12 - A constant presented as a runtime knob

**Mechanism.** A local `const bool` or a `static` variable placed in a namespace
named after console variables, with no console-variable registration.

**Why it is silent.** It compiles and behaves as the constant it is. The naming is
the only thing that lies, and naming is not checked by anything.

**Why the obvious check misses it.** The namespace name contains the word an
engineer greps for. Searching for the knob finds the declaration, which looks
exactly like the seven real registrations elsewhere in the project.

**Symptom.** Engineers try to change behaviour from the console and cannot. Time is
lost concluding that the console, the build, or the module is broken.

**Detect.** Compare pseudo-knobs against real registrations:

```bash
rg -n "^namespace \w*Cvar\w*" Source/          # namespaces that promise knobs
rg -c "FAutoConsoleVariableRef" Source/        # registrations that deliver them
```

Note the trap: searching for the literal `namespace Cvars` finds nothing, because
real names are prefixed (`FooManagerCvars`). The first draft of this recipe
returned zero hits and would have been read as "no such problem here". In the
audited project the corrected recipe finds one such namespace against eight real
registrations, and inside that namespace only a console *command* is registered —
the two variables beside it are plain constants.

**Guardrail.** If it must be tunable, register it as a real console variable.
Otherwise do not name its scope after one.

---

### GC-13 - A collection that is iterated but never filled

**Mechanism.** A local container is declared, immediately looped over, and never
populated — usually with a comment where the population belongs.

**Why it is silent.** A loop over an empty container is a no-op, which is
indistinguishable from a loop whose input happens to be empty right now.

**Why the obvious check misses it.** The loop body is real code, often including
error handling and logging, so the feature reads as implemented. There is even a
warning path for invalid entries — which can never fire, because there are no
entries.

**Symptom.** A named feature ("always loaded cues") that has no inputs and
therefore no effect, while appearing complete in review.

**Detect.** Find containers declared and iterated within a few lines, with no
insertion between:

```bash
rg -n -A6 "T(Array|Set)<\w+>\s+\w+;" Source/ | rg -n "for\s*\("
```

For each hit, search the same scope for `Add|Emplace|Append|Insert` on that name.
None means the loop is decorative.

**Guardrail.** A loop over an empty local is a review blocker. If the population is
future work, the loop is future work too.

---

### GC-14 - Feature-plugin cue path registered too late

**Mechanism.** Registration is performed on feature activation, after the manager
has already built its tag-to-asset index.

**Why it is silent.** Registration succeeds. The path is in the list. It is simply
not in the *index*, and no error distinguishes those two states.

**Why the obvious check misses it.** In the editor, incidental rescans — asset
saves, hot reloads, content browser operations — rebuild the index often enough
that the cues appear to work. The failure is specific to a cold packaged run.

**Symptom.** A plugin's cues are invisible in a packaged build and fine in the
editor. The classic "works on my machine" that is actually "works in my editor".

**Detect.** Find where cue paths are added and which lifecycle phase the call sits
in:

```bash
rg -n "AddGameplayCueNotifyPath" Source/ -B12 \
  | rg -n "(OnGameFeatureRegistering|OnGameFeatureLoading|OnGameFeatureActivating|Activate)"
```

`Registering` is early enough; `Activating` is not. Also check the rescan flag: one
rescan per feature, not one per directory.

**Guardrail.** Register on the earliest lifecycle phase available, via a policy
observer rather than an activation hook. Batch the rescan: add all paths, rebuild
once. The audited project does exactly this, and its feature action deliberately
has no activation body at all.

---

### GC-15 - Asymmetric manager access across the lifecycle

**Mechanism.** Registration goes through a subclassed manager; removal goes through
the engine base class.

**Why it is silent.** Both calls compile and both succeed, because the subclass
inherits the base method. As long as the subclass adds no bookkeeping, the two
paths are equivalent — today.

**Why the obvious check misses it.** The two lines are in different functions,
often hundreds of lines apart, and both read as "get the manager, call the
method". The asymmetry is only visible when you put the two resolution expressions
side by side.

**Symptom.** Nothing, until the subclass gains state. Then removal silently leaves
entries behind and the registry drifts across activation cycles.

**Detect.** Put the add and remove sites next to each other:

```bash
rg -n "(AddGameplayCueNotifyPath|RemoveGameplayCueNotifyPath)" Source/ -B4 \
  | rg -n "(GetGameplayCueManager|UAbilitySystemGlobals|Cast<)"
```

Different resolution expressions on the two sides is the defect.

**Guardrail.** Resolve the manager the same way on both sides, and assert the
removal count. The audited project asserts the count — that assertion is the
mitigating factor and the part worth copying.

---

### GC-16 - Registry refresh on the way in but not on the way out

**Mechanism.** The primary-asset registration is refreshed when paths are added and
not when they are removed.

**Why it is silent.** A stale registration describes directories that no longer
exist. Asset lookups against them fail the same way a genuinely empty directory
fails: nothing found, no error.

**Why the obvious check misses it.** The refresh call on the add side is visible
and correct. Its absence on the remove side is one missing line in a function that
otherwise does everything right, including asserting its own removal count.

**Symptom.** Divergence that accumulates across feature activation cycles. Path
counts do not return to baseline after activate, deactivate, activate.

**Detect.** Count refresh calls against path-set mutations:

```bash
rg -n "RefreshGameplayCuePrimaryAsset" Source/ -B15 \
  | rg -n "(Registering|Unregistering|Add|Remove)"
```

A refresh on the registering path with no counterpart on unregistering is the
defect. Confirm behaviourally: activate, deactivate, activate a feature and
compare path counts.

**Guardrail.** Refresh on every path-set change, in both directions.

---

### GC-17 - Lossy payload conversion helper

**Mechanism.** A helper that converts between a message struct and cue parameters
drops fields.

**Why it is silent.** The conversion produces a valid, well-formed result. The
missing field arrives as its default value, which for a tag container is empty —
and empty is a legal value that means "no tags".

**Why the obvious check misses it.** The function has a name that promises a
conversion, a signature that mentions both types, and a body that assigns most
fields. Review confirms "yes, this converts". Only a field-by-field round trip
shows the hole.

**Symptom.** A field populated at the sender and empty at the receiver, on every
client, with no warning. Investigated as a replication bug for as long as it takes
to read the helper.

**Detect.** Read every conversion function field by field, and treat every
unfinished-work comment inside one as a declaration that the field is not carried:

```bash
rg -n -A20 "(ToCueParameters|FromCueParameters|VerbMessageTo|CueParametersTo)" Source/ \
  | rg -n "(TODO|FIXME|\?\?\?)"
```

In the audited project this finds the same field dropped in both directions, each
marked with its own comment.

**Guardrail.** Verify the round trip field by field before relying on any field.
Treat any unfinished-work comment in a conversion function as "this field is not
carried".

---

### GC-18 - Concluding "unused" from absent C++ callers

**Mechanism.** A Blueprint-callable function's call sites can live in binary asset
graphs, which are not text-searchable.

**Why it is silent.** The search is clean. Zero hits is a definite-looking answer,
and definite-looking answers are the ones people act on.

**Why the obvious check misses it.** The obvious check *is* the problem: `rg`
searches text, and the callers are not text. The tool answers the question it was
asked — "where does this string appear in source?" — which is not the question the
engineer meant.

**Symptom.** Code deleted as dead breaks a Blueprint at runtime, discovered after
the fact, usually by a designer.

**Detect.** For any Blueprint-exposed symbol, treat source search as inconclusive
by construction:

```bash
rg -n "UFUNCTION\(.*Blueprint(Callable|ImplementableEvent|NativeEvent)" Source/ -A2
```

Anything on that list needs the editor's reference viewer before removal. An empty
`rg` result proves the pattern, not the absence.

**Guardrail.** "No C++ callers" is not evidence of disuse for a Blueprint-exposed
symbol. Record it as an open question, not as dead code — which is exactly what the
audit did with the helpers from GC-17.

---

### GC-19 - Cue tag parked in the wrong namespace

**Mechanism.** A tag is declared next to the notify asset that happens to implement
it, rather than in the namespace that owns the concept.

**Why it is silent.** The tag works. Its location is a naming decision, and naming
decisions have no runtime behaviour — until someone tries to fix one.

**Why the obvious check misses it.** Nothing validates that a tag's namespace
matches its meaning. The only record that the placement is wrong is, at best, a
comment written by the person who did it.

**Symptom.** Moving it later requires a redirect. Without redirects, every asset
referencing it silently loses the reference — the rename is not blocked, it is
merely destructive.

**Detect.** Read the tag declarations for confessions, then check whether the
project has any migration mechanism at all:

```bash
rg -n "DevComment=.*(needs to move|wrong|temporary|should be)" Config/
rg -c "GameplayTagRedirects" Config/
```

In the audited project the first search finds a tag whose own comment says it is
misplaced, and the second returns zero — the tag cannot be moved without breaking
references.

**Guardrail.** Cue tags follow the concept, not the asset location. Add the
redirect in the same commit as any move, and make sure a redirect mechanism exists
before you need it.

---

### GC-20 - Editor measurements treated as representative of cue loading cost

**Mechanism.** The editor loads both the client and the server asset bundles.

**Why it is silent.** The measurement completes and produces a number. Numbers
from a profiler carry an authority that their provenance does not.

**Why the obvious check misses it.** The condition that causes it is one clause in
one branch of the bundle-selection logic, in a different subsystem from the one
being measured. Nobody profiling cue residency reads the experience loader.

**Symptom.** Memory and load-time figures that describe no shipping configuration.
Cue residency in particular is overstated, and budgets built on it are wrong in the
safe direction until the day they are not.

**Detect.** Read the bundle-selection branch before trusting any in-editor asset
memory number:

```bash
rg -n "GIsEditor\s*\|\|" Source/ -A4
```

If the editor branch unions both bundle sets, editor measurements are usable for
direction of change only.

**Guardrail.** Use editor measurements for direction of change. Absolute cue
loading cost requires a packaged build, and any budget quoted without one carries
that caveat in writing.
