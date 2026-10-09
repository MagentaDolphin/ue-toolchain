# Failure modes: game settings and performance

Nine ways a settings layer stores a value the player chose and does nothing with
it.

The shared property is unusual and worth stating carefully: **in this area the
framework is usually right and the wiring is usually missing.** Every finding
below sits at a seam — between a model and a property path, between a stored
value and the code that applies it, between a complete pipeline and the caller it
never got. None of them is a design flaw in the mechanism they belong to.

That matters for adoption, which is what this skill is for: the correct response
to this list is *copy the framework, audit the wiring*, not *write your own*.

Recipes use `rg` from a project source root and were executed against the audited
project while this file was written.

---

## Binding

### GS-01 - A property path the compiler does not check

**Mechanism.** Settings bind to storage through a stringified path to a getter
and setter, resolved by reflection at runtime. A macro checks that the function
*name* exists; nothing checks the return type, the parameter count or constness.

**Why it is silent.** A mismatched path fails at initialization with an
assertion — and assertions are compiled out of shipping builds. In shipping, a
broken binding is a setting that reads a default and writes nowhere.

**Why the obvious check misses it.** The macro's name contains "checked", and it
genuinely does check something. Review sees a compile-time-looking construct and
stops. The remaining gap is invisible until the types diverge, which happens
during a refactor rather than at authoring time.

**Symptom.** In development, an assertion when the settings screen opens — often
dismissed as unrelated. In shipping, a setting that silently does nothing, which
is indistinguishable from a setting that is not implemented.

**Detect.** Find the path-building macros and confirm the failure mode of the
resolver, then check whether anything validates paths outside the editor:

```bash
rg -n "GET_FUNCTION_NAME_STRING_CHECKED|FCachedPropertyPath|PropertyPathHelpers" \
  --glob "*.h" --glob "*.cpp" .
rg -n -B4 "ensure|checkf" --glob "*.cpp" . | rg -i "getter|setter|propertypath"
rg -n "UE_BUILD_SHIPPING" --glob "*.cpp" . | rg -i "ensure"
```

**Guardrail.** Validate every path during registry initialization, report the
**setting's developer name** rather than a reflection error, and run that
validation in an automated test so it fails a build rather than a play session.

---

### GS-02 - Uniqueness enforced on the identifier, nothing enforced on the pair

**Mechanism.** Settings carry a stable developer name, and the registry checks it
is unique. Nothing checks that the name still matches the property path it binds.

**Why it is silent.** Both halves are individually valid: a unique name and a
resolvable path. A setting named for one property and bound to another works
perfectly and is wrong.

**Why the obvious check misses it.** The uniqueness check exists and passes,
which answers "are the identifiers sane?". Copy-paste between two settings
changes the display text and leaves the path — and the resulting setting looks
correct in every view except behaviour.

**Symptom.** Two settings that move together, or one that changes something the
player did not select. Reported as "the wrong option is wired up", investigated
in the widget layer.

**Detect.** Extract name/path pairs and eyeball the mismatches:

```bash
rg -n -B2 -A6 "SetDevName\(" --glob "*.cpp" . \
  | rg "SetDevName|SetDynamicGetter|SetDynamicSetter"
```

Read the triples. A developer name and a getter that share no token is the
finding — crude, and it catches the copy-paste error that produces this.

**Guardrail.** Assert the correspondence in a test that walks the registry, or
generate the name from the path. A convention nothing enforces is a convention
that has already been broken somewhere.

---

## Ownership

### GS-03 - A per-player accessor that returns a global singleton

**Mechanism.** The local player exposes an accessor for its settings; the
implementation returns a process-wide singleton.

**Why it is silent.** With one local player it is correct in every observable
way. The abstraction is only wrong when a second player exists, which is a
configuration most testing never enters.

**Why the obvious check misses it.** Every call site reads correctly — a player
asking for its settings. The defect is one line inside an accessor that nobody
reads twice, because accessors are the least interesting code in a file.

**Symptom.** In split-screen, the second player edits the first player's
settings. Usually discovered not as a bug but as a growing population of "only
the primary player may change this" conditions, added one at a time by people
working around a cause nobody named.

**Detect.** Read the body of every per-player settings accessor:

```bash
rg -n -A4 "::Get\w*Settings\(\) const|::Get\w*Settings\(\)" --glob "*.cpp" . \
  | rg -i "::Get\(\)|GEngine->|StaticClass"
rg -n "PlayingAsPrimaryPlayer|IsPrimaryPlayer" --glob "*.cpp" . | wc -l
```

The second count is the corroborating signal: a large number of primary-player
conditions in a project that claims per-player settings means the claim is not
true. In the audited project the accessor returns a global object, and the
conditions are numerous.

**Guardrail.** Decide per value whether it is machine-scoped or player-scoped,
and let the accessor's return type say which. If a value must be global, name the
accessor globally — the honest name prevents the workarounds.

---

### GS-04 - Player preferences stored in machine-scoped storage

**Mechanism.** A value that is clearly a personal preference — volume, for
instance — lives in the machine-local store because that is where the subsystem
applying it happens to read from.

**Why it is silent.** It works for one player on one machine, which is the
overwhelmingly common case. The value persists, applies, and survives restart.

**Why the obvious check misses it.** The placement follows the *implementation*
rather than the *semantics*, and the implementation reason is real: the applying
code is machine-global. A reviewer asking "does this work?" gets yes.

**Symptom.** Preferences that do not follow the player to another machine, and
two local players who cannot have different values. Discovered when cloud saves
or split-screen are added, long after the placement was set.

**Detect.** Classify the fields of both stores against the ownership test:

```bash
rg -n "UPROPERTY\(Config\)" -A2 --glob "*.h" <local-settings>.h | rg "\w+ \w+;"
rg -n "UPROPERTY\(\)" -A2 --glob "*.h" <shared-settings>.h | rg "\w+ \w+;"
```

For each field ask the four ownership questions from the skill. In the audited
project the audio volumes sit in machine-local storage, and the registry that
builds the audio screen reaches into both stores from adjacent lines.

**Guardrail.** Place by semantics, then solve the application problem. If the
applying subsystem is global, the setting can still be player-scoped with the
primary player's value applied — that is a deliberate policy rather than an
accident of storage.

---

## Application

### GS-05 - A global apply invoked from a change notification

**Mechanism.** Changing a setting immediately calls the heavyweight global apply
path from inside the change handler, rather than staging the value until the
player presses apply.

**Why it is silent.** The result is correct and even feels responsive — the
player sees the change instantly. Cancel still restores the value, so the
transaction is not broken, only leaky.

**Why the obvious check misses it.** It is three lines in an edit condition,
placed where a reviewer expects a condition rather than an action. The cost only
appears with a setting a player can scrub — a slider makes it one global reapply
per tick.

**Symptom.** Stutter while adjusting a quality setting; a visible flash on values
the player then cancels; and, for expensive channels, a hitch per change.

**Detect.** Find application calls inside notification paths, and check for the
tell:

```bash
rg -n -B6 "ApplyScalabilitySettings|ApplySettings|SetQualityLevels" --glob "*.cpp" . \
  | rg "SettingChanged|OnSettingChanged|NotifySettingChanged"
rg -n -i "//\s*TODO.*(for now|immediately)" --glob "*.cpp" .
```

The second command is the high-yield one: in the audited project the immediate
apply carries a comment saying "for now", which converts a judgement call into a
confirmed finding.

**Guardrail.** Stage by default; preview deliberately and cheaply; apply on
apply. Treat "for now" on a global apply path as a scheduled item, not a note.

---

### GS-06 - A stored preference with no application code

**Mechanism.** A value is exposed, edited, persisted and loaded. The function
that would apply it has an empty body.

**Why it is silent.** Every visible part of the round trip works: the slider
moves, the value saves, it comes back after restart. Only the effect is missing,
and the effect is subjective — sensitivity, in the audited case.

**Why the obvious check misses it.** The apply function exists and is called. A
review of the settings layer finds a complete implementation; the emptiness is in
a body that the caller has no reason to open. And because the value *is* readable,
game code may consume it directly elsewhere, making the empty function neither
wrong nor sufficient.

**Symptom.** A player changes a preference, the UI confirms it, and nothing feels
different. Support cannot reproduce it because the value really is stored.

**Detect.** Find apply functions with empty bodies:

```bash
rg -n -A3 "void \w+::Apply\w+\(\)" --glob "*.cpp" . | rg -B2 "^\s*\}"
```

Then, for each stored preference, find its consumer:

```bash
V='MouseSensitivityX'
rg -n "\b$V\b" --glob "*.cpp" --glob "*.h" . | rg -v "UPROPERTY|Set$V|Get$V"
```

No consumer outside the accessors means the value goes nowhere.

**Guardrail.** A setting ships with its consumer, in the same change. If
application is intentionally the game's responsibility rather than the
framework's, delete the empty function — an empty function is a claim.

---

## Wiring

### GS-07 - A composition part that is read six times and never assigned

**Mechanism.** A device-profile name is composed from parts — base platform, a
mode suffix, a user choice — with fallback through progressively shorter
combinations. One part is declared as a local, read repeatedly, and never
written.

**Why it is silent.** The fallback is designed to handle a missing part, and it
does. Every path produces a valid profile name; the composition simply never
takes the branches that use the absent part.

**Why the obvious check misses it.** The variable appears in six places,
including a log line that prints it. Any "is this used?" search answers yes
loudly. The absent half is the **writer**, and no default tool asks that
question — this is the canonical shape from `ue-reference-project-adoption`,
found here in a subsystem where the consequence is a whole feature that does not
exist.

**Symptom.** Documentation and code structure both indicate that a game mode can
select its own device profile. It cannot. A team planning per-mode performance
profiles discovers this after designing around it.

**Detect.** For any composed name, count reads against writes:

```bash
V='ExperienceSuffix'
rg -n "\b$V\b" --glob "*.cpp" .
rg -n "\b$V\b\s*=[^=]" --glob "*.cpp" .
```

Reads with no assignment is the finding. In the audited project the first command
returns six lines — a declaration, four reads and a log — and the second returns
nothing but the declaration itself, which the authors annotated with a comment
saying nothing sets it.

**Guardrail.** Do not ship a composition part with no producer. If it is
scaffolding for a planned feature, say so where a reader of the *composition*
will see it, not only at the declaration.

---

### GS-08 - A complete pipeline with no caller

**Mechanism.** Automatic quality detection is fully implemented: a capability
check, a benchmark, threshold mapping, application and save. The function that
decides whether to run it at startup has no caller anywhere.

**Why it is silent.** The manual path works. A player who presses the button gets
correct auto-detection, so the feature demonstrably functions — just never on its
own.

**Why the obvious check misses it.** Every component is present and testable, and
unit tests of the threshold mapping pass. "Do we support automatic quality?"
answers yes from any angle except the one that matters: who starts it.

**Symptom.** First-run experience uses default quality on every machine. Nobody
notices, because developers' machines default acceptably and the button exists.

**Detect.** For the decision function, distinguish declaration from call:

```bash
F='ShouldRunAutoBenchmarkAtStartup'
rg -n "\b$F\b" --glob "*.h" --glob "*.cpp" .
```

Exactly two hits — the declaration and the definition — is the finding. Extend to
content if the project can call functions from assets, and record the result as
open if you cannot inspect them.

**Guardrail.** Every entry-point function gets a **call-site test**, not only a
unit test of what it computes. The mapping was never the part at risk.

---

### GS-09 - A size guard whose count nobody knows

**Mechanism.** Code enumerates every member of an engine struct — copying,
clamping, maximising quality levels field by field — and protects itself with a
compile-time assertion on the struct's size.

**Why it is silent.** It is correct, and it is good practice: after an engine
upgrade adds a channel, the build breaks instead of silently ignoring it.

**Why the obvious check misses it.** Nothing is wrong here. The hazard is
procedural: the guard fires during an upgrade, under time pressure, and the
person who bumps the number needs to know **how many functions** must be reviewed.
That number is not written anywhere near the assertion.

**Symptom.** An engine upgrade where the size constant is updated and one of the
five enumerating functions is not, silently dropping a quality channel — exactly
the failure the guard was written to prevent.

**Detect.** Count the guards and the functions they protect before upgrading:

```bash
rg -n "static_assert\(sizeof\(" --glob "*.cpp" --glob "*.h" .
rg -c "static_assert\(sizeof\(Scalability::FQualityLevels\)" --glob "*.cpp" .
```

In the audited project this returns **five** sites for one struct. Five is the
number an upgrader needs and would otherwise have to discover by grepping mid-fix.

**Guardrail.** Write the count and the list of functions into the assertion
message. The guard is only as good as the instruction it gives the person it
stops.
