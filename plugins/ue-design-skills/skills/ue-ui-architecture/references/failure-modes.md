# Failure modes: UI architecture

Fourteen ways a layered, slot-based UI puts the wrong thing in the wrong place,
in the wrong order, or nowhere at all — without reporting anything.

The shared property: **this architecture is built out of joins that nothing
checks.** A layer is a tag looked up in a map. A slot is a tag matched against
another tag. A contribution is a class pointer that may or may not be loaded.
Every one of those joins fails by producing nothing, and producing nothing is
also what a correctly configured, currently-empty UI looks like.

A second property worth stating: **UI failures are reported by people, not by
tools.** Nobody writes a test that asserts a widget appeared in a slot. So the
detection recipes below matter more here than in most areas, because they are
frequently the only instrument that exists.

Recipes use `rg` from a project root and were executed against the audited
project while this file was written.

---

## Ordering and placement

### UI-01 - A priority field that never sorts

**Mechanism.** The extension API accepts a priority on every registration
overload, stores it on the entry, and copies it into the request struct handed to
the slot widget. Nothing ever compares two priorities.

**Why it is silent.** An order is produced on every run — registration order —
and it is stable for as long as the set of contributors is stable. The UI looks
deliberate. Nothing is missing; things are merely arranged by accident.

**Why the obvious check misses it.** The value travels through the entire public
surface: eight registration entry points, the entry struct, the request struct.
Any review asking "is priority used?" finds a dozen sites and stops. The right
question is much narrower — *does it appear inside a sort or a comparison?* — and
that is not a question anyone thinks to ask about a field that is so obviously
plumbed.

**Symptom.** Widget order inside a slot changes between runs and between
machines. In a plugin-based project registration order is feature activation
order, so the symptom reads as a race condition and gets investigated in the
loading system.

**Detect.** Count the plumbing, then look for the comparison:

```bash
rg -n "\bPriority\b" --glob "*.cpp" --glob "*.h" <ui-extension-module>/ | wc -l
rg -n "Sort|StableSort|Algo::" <ui-extension-module>/ | wc -l
```

In the audited project the first number was substantial and **the second was
exactly zero** — no sort of any kind exists in the module. A removal that uses
swap-with-last compounds it by reordering the array on every unregistration.

**Guardrail.** An ordering field ships with its comparator in the same change, or
it does not ship. If order genuinely does not matter, do not expose a field that
promises it — the field is a more expensive lie than the missing feature.

---

### UI-02 - A duplicated key in the plugin descriptor silently drops a dependency

**Mechanism.** The descriptor is JSON. It contains the dependency array key twice.
By JSON semantics the second occurrence replaces the first, so half the declared
dependencies do not exist as far as any parser is concerned.

**Why it is silent.** The project builds and runs, because the lost dependency
arrives transitively through the surviving one and is also enabled at the project
level. The declaration was redundant in this configuration — which is exactly why
nobody notices it is gone.

**Why the obvious check misses it.** Reading the file shows both blocks. A human
reader sees two lists and mentally unions them; a parser sees one key assigned
twice and keeps the last. The file *looks* more correct than it is, and no editor
or build step warns about duplicate keys.

**Symptom.** Nothing, until the transitive path disappears — someone disables the
intermediate plugin, or extracts this plugin into another project. Then a
dependency that the descriptor appears to declare is simply not there.

**Detect.** Do not read it. Parse it, and compare against the raw text:

```bash
rg -c '"Plugins"' <plugin>/<Plugin>.uplugin        # occurrences in the text
python -c "import json,sys; d=json.load(open(sys.argv[1],encoding='utf-8-sig')); \
print([p.get('Name') for p in d.get('Plugins',[])])" <plugin>/<Plugin>.uplugin
```

A count above one from the first command means the second command is
authoritative. In the audited project the text contained two dependency blocks
and the parser reported exactly one surviving dependency — the other was
discarded. This is the single cheapest recipe in this file and it generalises to
every hand-edited descriptor in a project.

**Guardrail.** Validate every descriptor by parsing it in CI, not by reading it.
Assert that the parsed dependency set equals the intended set.

---

### UI-03 - Unknown layer tag resolves to a silent null

**Mechanism.** Pushing a screen looks the layer tag up in a map. A miss returns
null and the push does not happen.

**Why it is silent.** Returning null is the correct behaviour for a container
that does not exist. The caller usually ignores the return value, because in the
working case it is a widget nobody needs a reference to.

**Why the obvious check misses it.** The call site reads perfectly: a tag, a
class, a push. The tag is a constant that exists in the vocabulary, so it is
spelled correctly — it simply names a layer that this particular root layout did
not register. Layers are registered from a Blueprint layout asset, which no code
search can inspect, so the set of valid tags is not knowable from source.

**Symptom.** A screen never appears. No log, no assertion. Investigation starts
from the screen's own class, which is fine, and from the push call, which is also
fine.

**Detect.** Compare the tags that are pushed against the tags that are
registered, accepting that the second half may require the editor:

```bash
rg -o -N 'PushWidgetToLayerStack\w*\(\s*([A-Za-z_:]+)' -r '$1' --glob "*.cpp" .
rg -n "RegisterLayer" --glob "*.cpp" --glob "*.h" .
rg -o -N 'Tag="(UI\.Layer\.[^"]+)"' -r '$1' Config/ | sort -u
```

The third command gives the declared vocabulary; if a pushed tag is not in it,
the defect is certain. If it is in the vocabulary, the layout asset still has to
be checked in the editor — which is the finding in itself.

**Guardrail.** Make the push assert or log an error on an unknown layer, naming
the tag and listing the registered ones. A lookup miss on a hardcoded key is
never a legitimate runtime state.

---

## Contribution lifetime

### UI-04 - Contribution class resolved with a bare accessor and no fallback

**Mechanism.** The feature action resolves its widget classes with an accessor
that returns whatever is already loaded, relying on asset bundles to have loaded
them, and passes the result on without checking.

**Why it is silent.** When bundles work — which is always, inside the pipeline
that was designed for them — the classes are loaded and everything is correct. A
null is rejected downstream with at most a verbose log.

**Why the obvious check misses it.** The bundle annotation is right there on the
property, so the loading question looks answered. The failure requires the action
to run outside its intended pipeline, which is not a state the code was reviewed
against.

**Symptom.** Widgets silently missing for one feature, in one configuration
— typically a packaged build, or a manual invocation of the action — while
everything works in the editor.

**Detect.** Find bare accessors on soft references in contribution paths:

```bash
rg -n "\.Get\(\)" --glob "*.cpp" . | rg -i "widget|layout|class"
rg -n -B4 "\.Get\(\)" --glob "*.cpp" . | rg "AssetBundles"
```

Then check each hit for a null branch. In the audited project both contribution
loops used the bare accessor; the layout loop tested for null and the slot loop
did not — the null travelled one function further and was rejected there with a
verbose-level log.

**Guardrail.** Either load explicitly with a failure path, or check the result
and log at warning level with the asset name. "The bundle guarantees it" is a
statement about one pipeline, not about the code.

---

### UI-05 - Two teardown paths with different strength

**Mechanism.** The feature action removes its two kinds of contribution
differently: slot extensions are unregistered, which synchronously removes the
entry widget; layouts are asked to deactivate, which is a request the stack may
honour later or differently.

**Why it is silent.** Both calls succeed. Deactivation is a real operation with a
visible effect, so the layout does disappear from view in the common case.
Whether the stack still retains it, and whether it will reactivate when the layer
is next popped to, is not observable from the action.

**Why the obvious check misses it.** Both halves of teardown exist and are
symmetric in shape — a loop over layouts, a loop over handles. Reading the
function gives no reason to suspect that one loop is weaker than the other. The
difference is in the semantics of two APIs in a different plugin.

**Symptom.** A layout that reappears, or that is still in the stack's history
after its owning feature is gone. On reactivation the layer may hold two.

**Detect.** Compare the verbs used in the two removal loops:

```bash
rg -n -A20 "::Remove\w*\(" --glob "*.cpp" . | rg "Deactivate|Unregister|RemoveWidget"
```

A `Deactivate` in one loop and an `Unregister` in the other is the finding.
Confirm at runtime: activate, deactivate, reactivate, and count entries in both
the slot and the layer.

**Guardrail.** Removal means removal. If the stack API distinguishes deactivation
from removal, call the removing one and verify the stack no longer retains the
widget. Assert the count returns to baseline.

---

### UI-06 - Manual garbage-collection reference tracking

**Mechanism.** The object held by a registration is not a reflected property, so
the subsystem walks its own maps in the reference-collection hook to keep those
objects alive.

**Why it is silent.** It works, exactly and completely, for as long as the hook
matches the data structure. There is no degraded mode — either the object is
collected or it is not.

**Why the obvious check misses it.** The hook is correct when written and is far
from the data structure it mirrors. Adding a third map, or a new object-holding
field, is a local change that does not visibly relate to a function elsewhere in
the file. Nothing links them.

**Symptom.** After a refactor, an object is collected while still registered.
Symptoms are arbitrary: a null contribution, a crash on a stale pointer, a
contribution that silently stops matching.

**Detect.** Find manual reference collection and check it covers every container:

```bash
rg -n -A15 "AddReferencedObjects" --glob "*.cpp" .
rg -n "TMap<.*TSharedPtr<|TObjectPtr<\w+> \w+;" --glob "*.h" <ui-extension-module>/
```

Compare the containers walked by the first against the containers declared by the
second. Any container holding objects and not walked is a leak of correctness.

**Guardrail.** Prefer reflected properties. Where manual collection is
unavoidable, put the hook immediately adjacent to the declarations it mirrors and
add a comment at each declaration pointing at it.

---

### UI-07 - Context matched by pointer, held weakly

**Mechanism.** A contribution is scoped to a context object — usually a local
player — and matching compares pointers. The stored reference is weak.

**Why it is silent.** When the context dies, the contribution stops matching
anything, which looks exactly like a contribution that was correctly removed. No
stale widget appears, so nothing draws attention.

**Why the obvious check misses it.** The weak pointer is the *right* choice and
prevents the dangerous failure. What it does not do is remove the record, and
"does this leak memory?" is answered by the weak pointer while "does this leak
records?" is not asked at all.

**Symptom.** Registration maps that grow across sessions with entries that can
never match again. Only visible if something counts them.

**Detect.** Find weak context fields and check for a cleanup path keyed on their
expiry:

```bash
rg -n "TWeakObjectPtr<UObject>\s+ContextObject|ContextObject ==" --glob "*.h" --glob "*.cpp" .
rg -n "IsExplicitlyNull|IsValid\(\)" --glob "*.cpp" <ui-extension-module>/
```

The finding is a comparison path with no eviction path. Confirm by logging map
sizes across a local-player add/remove cycle.

**Guardrail.** Evict on context expiry, or key the map by context so an entire
context can be dropped in one operation.

---

## Diagnosis surface

### UI-08 - Swapped logging branches

**Mechanism.** Two log statements in the two arms of a conditional have their
format strings exchanged: the branch that has a context logs the format without
it, and the branch that has none logs the format with it — printing a safe-name
of null.

**Why it is silent.** It is a log line. It costs nothing at runtime, breaks no
behaviour, and is emitted at verbose level, so it is invisible unless someone
turns the category up.

**Why the obvious check misses it.** Reviewers read log statements for the
message, not for which branch they are in. Both lines are individually plausible.
The defect only exists in the pairing, and the pairing is exactly what the eye
skips.

**Symptom.** When someone finally enables verbose logging — necessarily during a
difficult investigation — the log lies about which registrations have a context.
The cost is paid at the worst possible moment.

**Detect.** Read both arms of every logging conditional together:

```bash
rg -n -B3 -A8 "if\s*\(\s*ContextObject\s*\)" --glob "*.cpp" . | rg "UE_LOG|GetNameSafe"
```

Look for a format string mentioning the variable inside the branch where it is
null. In the audited project this is present and unmistakable once the two lines
are read side by side.

**Guardrail.** Log through one statement with a conditional argument rather than
two statements with divergent formats. One format string cannot disagree with
itself.

---

### UI-09 - Missing focus target caught by a warning, not an error

**Mechanism.** A screen that does not declare a focus target compiles with a
Blueprint warning.

**Why it is silent.** Warnings scroll. A project with any warning debt has
normalised them, and this one appears only when the specific widget is compiled.

**Why the obvious check misses it.** The check exists — someone wrote it
deliberately and worded it well. It is diligence that has been graded as
optional. The failure is not the absence of a check but its severity, which no
review of the checking code would flag.

**Symptom.** On a gamepad, opening the screen leaves focus nowhere: no
navigation, no visible selection, and often no way back. It is one of the most
expensive UI bugs to receive from a player and one of the cheapest to prevent.

**Detect.** Find the validation and check its severity, then find the screens
that would trip it:

```bash
rg -n -B4 -A8 "ValidateCompiledWidgetTree|ValidateCompiledDefaults" --glob "*.cpp" . \
  | rg "Warning|Error|Note"
rg -n "GetDesiredFocusTarget|BP_GetDesiredFocusTarget" --glob "*.cpp" --glob "*.h" .
```

A validation that emits a warning for a gamepad-blocking condition is the
finding.

**Guardrail.** Promote it to an error, or gate packaging on it. A check that
cannot fail a build is documentation with extra steps.

---

### UI-10 - The loading screen's only diagnostic is a string nobody must break

**Mechanism.** Arbitration polls a set of providers, each of which returns
whether it needs the screen and why. The accumulated reason is the sole
explanation for a stuck loading screen.

**Why it is silent.** A permanent loading screen *is* the failure, and it is
loud. The silence is in the cause: the screen is a correct response to a provider
that never releases.

**Why the obvious check misses it.** There is no artefact to inspect. The screen
is showing because at least one of a dozen conditions is true, and only one of
them names itself. A team that bypasses the interface with its own flag removes
even that.

**Symptom.** A build that hangs on the loading screen with no information, in a
configuration that cannot be attached to a debugger.

**Detect.** Enumerate the providers and check that nothing shows the screen
outside them:

```bash
rg -n "ShouldShowLoadingScreen" --glob "*.cpp" --glob "*.h" .
rg -n "AddViewportWidgetContent|bShowLoadingScreen|LoadingWidget" --glob "*.cpp" . \
  | rg -v "LoadingScreenManager"
```

The second command should be empty. Any hit is a path that shows or hides the
screen without contributing a reason, and it is the one you will be unable to
diagnose. In the audited project the arbitration enforced a non-empty reason with
an assertion — a design worth copying exactly.

**Guardrail.** One owner presents; everyone else reports need plus reason.
Require the reason with an assertion, and expose the current reason to a console
command.

---

### UI-11 - Forced collection at the moment control returns to the player

**Mechanism.** Hiding the loading screen forces a full garbage collection.

**Why it is silent.** It is deliberate, it is defensible, and it is not a bug. The
cost lands as a hitch precisely when the screen disappears, which is a moment the
player already expects to be uneven.

**Why the obvious check misses it.** Nobody profiles the loading screen. It is
infrastructure that ran before the thing you are measuring. The hitch is
attributed to the level, to shader compilation, or to streaming.

**Symptom.** A consistent stall at the first frame of gameplay that resists
explanation from gameplay profiling.

**Detect.** Find global side effects in the hide path:

```bash
rg -n -B6 -A6 "ForceGarbageCollection|SetBatchMode|SuspendHeartBeat|bDisableWorldRendering" \
  --glob "*.cpp" .
```

Every hit is a process-wide effect owned by the loading screen. Each may be
correct; all of them are worth knowing about before copying the subsystem.

**Guardrail.** Measure before adopting. If a forced collection is wanted, do it
while the screen is still up, not as it comes down.

---

### UI-12 - Behaviour that differs in the editor by design

**Mechanism.** The loading screen's input blocker declines to consume input when
running under the editor.

**Why it is silent.** It makes editor iteration bearable, which is why it was
written. The divergence is invisible because the editor is where everyone looks.

**Why the obvious check misses it.** Testing happens in the configuration that
has the exception. Confirming the difference requires running a packaged build
specifically to compare input behaviour during loading, which is not on anyone's
list.

**Symptom.** Input handled during loading behaves differently in a packaged
build. Bugs that only reproduce for QA, in a build the developer cannot iterate
on.

**Detect.** Find editor-conditional behaviour in shared runtime paths:

```bash
rg -n "GIsEditor|WITH_EDITOR" --glob "*.cpp" <loading-and-ui-modules>/ \
  | rg -v "^.*Editor.*\.cpp"
```

Each hit is a place where the editor is not representative. List them and decide
which matter; the point is to hold the list, not to remove it.

**Guardrail.** Keep a written list of deliberate editor divergences in the UI and
loading paths, and test each one in a packaged build at least once per milestone.

---

## Structure

### UI-13 - Layers used as z-order buckets

**Mechanism.** New layers are added to place widgets relative to each other,
rather than to express modality.

**Why it is silent.** It works. A new layer is one registration and one tag, and
the widget appears where intended.

**Why the obvious check misses it.** Each addition is individually reasonable and
locally minimal. The cost is structural and accrues over releases: input and
focus policy is per layer, so every added layer multiplies the modality matrix
that must be reasoned about and tested.

**Symptom.** Focus and input behaviour that nobody can predict, because there are
nine layers and the policy interaction between them was never designed.

**Detect.** Count layers against modalities:

```bash
rg -o -N 'Tag="(UI\.Layer\.[^"]+)"' -r '$1' Config/ Plugins/*/Config/ | sort -u
```

More than a handful, or names that describe position rather than modality, is the
finding. In the audited project there were exactly four, named for modality.

**Guardrail.** Layers express modality: gameplay, game menu, menu, modal. Relative
placement within one modality belongs to slots inside a layout, not to new layers.

---

### UI-14 - The composition is knowable only from binary assets

**Mechanism.** Layers are registered, and slots are placed, from widget assets.
Source contains the vocabulary and the API but not the arrangement.

**Why it is silent.** It is the intended design and its benefit is real: the
shell's layout is authored by designers without engineering involvement.

**Why the obvious check misses it.** Reading all the source and finding no
arrangement feels like an incomplete search rather than a property of the system.
Time is lost widening greps that cannot succeed.

**Symptom.** "Which layers exist?" and "which slots does the HUD have?" cannot be
answered from a repository checkout. Onboarding, audits and automated validation
all stop at this boundary.

**Detect.** Get what source can give, and mark the rest as open:

```bash
rg -o -N 'Tag="(UI\.(Layer|Slot)\.[^"]+)"' -r '$1' Config/ Plugins/*/Config/ | sort -u
rg -n "RegisterLayer|ExtensionPointTag" --glob "*.cpp" --glob "*.h" .
```

The first command yields the declared vocabulary — the set of names that *may*
exist. The mapping from those names to actual containers requires the editor.
**Record that as an open question rather than concluding from the empty result**;
this is the same rule as any other empty search, and it is the honest form of the
answer.

**Guardrail.** Emit the registered layer and slot inventory to the log at
startup, or to a console command. One dump converts a permanently unanswerable
question into a cheap one.
