# Failure modes: data-driven architecture

Ten ways a data graph is wrong while remaining perfectly valid.

The shared property: **data does not compile, so nothing rejects it.** A null
reference, an unregistered identifier, a missing bundle annotation, a
copy-pasted prototype and a field nobody reads are all well-formed assets. They
load. They cook. The only thing that can reject them is validation somebody
chose to write, and that validation is usually compiled out of the build where
it would matter.

A second property specific to this area, and the reason the first recipe is
first: **most of this layer is invisible to text search.** Definitions live in
binary assets; the values live on class defaults. A recipe that greps source
answers a question about the *schema*, not about the *data*. Several recipes
below therefore require the editor, and say so rather than pretending a grep
will do.

---

## Census

### DD-01 - Half the definition layer is invisible to the census

**Mechanism.** A definition layer can be built from two containers at once: data
asset instances, and Blueprint classes with no graph nodes whose values live on
the class default object. An inventory that queries for one container reports a
complete-looking number.

**Why it is silent.** The number is real, plausible, and internally consistent.
Nothing indicates it is partial — an inventory has no way to report the
containers it did not think to look in.

**Why the obvious check misses it.** "Find the data assets" is the correct
phrasing of the wrong question. The second container is not a data asset by class,
is not named like one, and appears in the content browser as a Blueprint. In the
audited reference this was not a corner case: **every** gameplay definition, item
definition and equipment definition lived in the second container.

**Symptom.** Audits, rename sweeps, memory budgets and dependency graphs that are
each individually correct and collectively wrong. Decisions get made on a census
that missed the most important layer.

**Detect.** Count both containers, from the editor — this cannot be done from
source:

```python
# editor-side, via the asset registry
ar = unreal.AssetRegistryHelpers.get_asset_registry()
# 1. instances deriving from the data asset base
# 2. blueprint classes whose native parent is a definition type,
#    then check node count on the generated class
```

From source you can only establish the *schema* — which types exist and which
are meant to be subclassed:

```bash
rg -n "class \w+ : public UPrimaryDataAsset|class \w+ : public UDataAsset" \
  --glob "*.h" .
rg -n "UCLASS\([^)]*Blueprintable" --glob "*.h" . | rg -i "definition|data"
```

**Guardrail.** Define "the data layer" as a set of *types*, not a set of asset
classes, and enumerate instances per type. Record the count per container so a
future reader can see which containers were searched.

---

### DD-02 - Reflection reports an empty object that is full

**Mechanism.** A generic property dump over a class default object returns
nothing, or almost nothing, for an object whose inherited fields are populated.

**Why it is silent.** An empty result is a legitimate answer — plenty of objects
genuinely have no properties set. The tool did not fail; it succeeded and
returned nothing.

**Why the obvious check misses it.** The check *is* the dump. Its output is
authoritative-looking structured data, and the natural conclusion — "this
definition is empty, so the values must live elsewhere" — sends the investigation
in a direction with no bottom.

**Symptom.** Hours spent looking for where the configuration "really" lives,
followed by a confident and wrong claim that a definition carries no data.

**Detect.** Never conclude from a generic dump. Read known fields by name,
driven by the schema you extracted from source:

```bash
# 1. get the field names from the C++ declaration
rg -n -A20 "class \w*ExperienceDefinition" --glob "*.h" . | rg "UPROPERTY" -A1
```

```python
# 2. editor-side, read each named field explicitly rather than enumerating
for field in ("GameFeaturesToEnable", "DefaultPawnData", "Actions", "ActionSets"):
    value = cdo.get_editor_property(field)
```

A field that a generic dump omitted and a named read returns is the finding, and
it invalidates every conclusion drawn from the dump.

**Guardrail.** Treat generic reflection as a discovery aid and named reads as
evidence. When reporting "this object has no data", state which method produced
that answer.

---

## Loading and boundaries

### DD-03 - Soft reference with no bundle annotation

**Mechanism.** A definition holds a soft reference to content needed only by one
role. Without a bundle annotation, nothing tells the asset manager to pull that
content in when the owner loads.

**Why it is silent.** In the editor everything is loaded anyway — commonly both
role bundles at once — so the reference resolves and the feature works. The
failure requires a build where only what was asked for is present.

**Why the obvious check misses it.** The property is correct C++ and the
reference is correct data. The annotation is optional metadata whose absence
looks like every other property that legitimately does not need one. Reviewing
the definition shows nothing missing.

**Symptom.** A feature that works in the editor and silently does nothing in a
packaged build, because a class pointer resolved to null and the code path that
uses it treats null as "nothing to do".

**Detect.** List soft references, list annotations, and compare:

```bash
rg -n "TSoftObjectPtr<|TSoftClassPtr<" --glob "*.h" . | wc -l
rg -no 'AssetBundles="[^"]*"' --glob "*.h" . | sed 's/.*AssetBundles=//' \
  | sort | uniq -c
```

The gap between the two counts is your exposure. In the audited reference the
whole project carried **ten** bundle annotations — two client-only and eight for
both roles — against a much larger population of soft references. Most of those
are loaded by other means; the point of the recipe is that it produces the short
list worth checking rather than a verdict.

**Guardrail.** Annotate at the declaration, beside the reference, and validate
that every soft reference in a definition family either carries an annotation or
is documented as loaded by its consumer.

---

### DD-04 - Bare accessor on a soft reference

**Mechanism.** The consumer resolves a soft reference with an accessor that
returns whatever is already loaded, and uses the result without checking.

**Why it is silent.** Inside the pipeline the annotation was designed for, the
asset is always loaded. The null path is unreachable in every configuration
anyone tests.

**Why the obvious check misses it.** The bundle annotation is visible on the
property, so the loading question appears answered. The accessor call is one
word and reads as a dereference, not as a decision.

**Symptom.** One feature's content silently missing, in one configuration, with
no log line naming the asset.

**Detect.** Find bare accessors on soft references in consumer code:

```bash
rg -n "\.Get\(\)" --glob "*.cpp" . | rg -i "class|widget|ability|component"
rg -n -A2 "\.Get\(\)" --glob "*.cpp" . | rg -c "if \(|ensure|check"
```

The finding is a resolve with no null branch. Compare against the same file's
other resolves — in the audited reference one loop tested for null and the
adjacent loop did not, which is the clearest possible evidence that the check was
intended.

**Guardrail.** Either load explicitly with a failure path, or check and log at
warning level with the asset name. "The bundle guarantees it" is a claim about
one pipeline, not about the code.

---

## Composition

### DD-05 - Inheritance used where composition was intended

**Mechanism.** A definition type is Blueprint-subclassable, so authors subclass
one definition from another to reuse its values, producing a chain of inherited
defaults.

**Why it is silent.** It works. Inherited defaults are a supported feature, and
the child behaves as the sum of the chain.

**Why the obvious check misses it.** Each subclass is individually reasonable and
locally minimal — it changes two fields. The cost is structural: values now come
from several assets that must be opened in sequence, and a change to a parent
silently alters every descendant.

**Symptom.** A definition whose effective configuration cannot be read from the
definition. Diffs that show nothing while behaviour changes.

**Detect.** Find whether the type permits subclassing, and whether validation
objects:

```bash
rg -n "UCLASS\([^)]*Blueprintable" --glob "*.h" . | rg -i "definition"
rg -n -B2 -A6 "IsDataValid" --glob "*.cpp" . | rg -i "parent|subclass|inherit"
```

The audited reference does this well and is worth copying exactly: its
definition validation **rejects Blueprint subclasses of Blueprint definitions**
and the error text names the alternative — use composition via action sets. A
validator that says what to do instead is worth several that only refuse.

**Guardrail.** Decide per definition type whether subclassing is legal. If it is
not, reject it in validation with a message naming the composition mechanism.

---

### DD-06 - An action set that is really a parent class

**Mechanism.** Reusable slices are introduced, and then one slice starts
depending on being applied after another, or on values from a third.

**Why it is silent.** Order is stable in practice, because it comes from a list
that rarely changes. The coupling produces correct behaviour for as long as
nobody reorders anything.

**Why the obvious check misses it.** Composition was adopted specifically to
avoid ordering questions, so nobody looks for one. The dependency is not
expressed anywhere — it exists only in the fact that the current order works.

**Symptom.** Reordering a list, or reusing one slice without its neighbour,
breaks a feature that has no visible relationship to the change.

**Detect.** Look for actions that read state another action writes:

```bash
rg -n "class UGameFeatureAction_\w+" --glob "*.h" . -A30 \
  | rg "FindComponentByClass|GetSubsystem|Find\w+ForActor"
```

Every hit is an action that consumes something it did not create — a candidate
ordering dependency. For each, ask what happens if it runs first.

**Guardrail.** An action set is a set, not a sequence. If order matters, make it
explicit — a phase, a prerequisite declaration, or a single combined action — and
never leave it implied by list position.

---

## Content correctness

### DD-07 - Production data references the wrong definition

**Mechanism.** A presentation asset is duplicated to make a new one, and the
reference inside it is not updated. The copy points at the original's definition.

**Why it is silent.** Both assets are valid, both load, and the reference is a
real object of the right type. Nothing in the graph is broken; it simply says
something untrue.

**Why the obvious check misses it.** Validation checks that references are
non-null and correctly typed, which this passes. Confirming it means comparing
the *meaning* of two assets — that a health pickup should reference a health
item — and no type system encodes that.

**Symptom.** Picking up one thing and receiving another. In the audited
reference, two health pickups reference the pistol item definition. It ships.

**Detect.** This one is a cross-family check, and it needs the editor:

```python
# editor-side: for each pickup definition, compare its presentation identity
# against the item definition it references
for pickup in pickup_definitions:
    item = pickup.get_editor_property("InventoryItemDefinition")
    # heuristic that actually works: does the pickup asset's name share a token
    # with the item definition's name?
```

The heuristic is crude and that is the point — a crude cross-family check finds
copy-paste errors that no type check can. Add it to validation and let it produce
warnings a human triages.

**Guardrail.** Every cross-family reference gets a semantic check, even a weak
one. Also: keep prototype content out of production roots so that a naming-based
check has a chance.

---

### DD-08 - Fields that exist, are authored, and are never read

**Mechanism.** A definition exposes extension fields for future use. They are
never wired to a consumer.

**Why it is silent.** An unread field costs nothing and looks like configuration.
Its default is usually the correct behaviour, so leaving it empty is right.

**Why the obvious check misses it.** The field is declared, is editable, and
appears next to fields that do work. "Is this used?" answers yes on the
declaration. Only searching for a *reader* answers correctly — and unlike the
same failure in C++, the reader may be in a Blueprint graph that no text search
can inspect, so a negative result is weaker here.

**Symptom.** A designer configures a field and observes no effect. Because the
consumer may be in a binary asset, the investigation cannot conclude from source
alone, and often stops with "it must do something".

**Detect.** From source, find declaration-without-reader candidates; then confirm
in the editor:

```bash
F='ExtraArgs'
rg -n "\b$F\b" --glob "*.h" --glob "*.cpp" .
```

A single hit — the declaration — makes the field a candidate. **Do not conclude
it is dead**: check the editor's reference viewer for Blueprint consumers before
deleting. In the audited reference several such fields were empty in every
instance, which is evidence about usage but not about wiring.

**Guardrail.** Do not ship an editable field with no consumer. If it exists for
forward compatibility, mark it as such where the designer sees it, not only in a
commit message.

---

## Validation

### DD-09 - Validation compiled out of the build that needs it

**Mechanism.** Data validation is written as editor-only, so it runs when an
author opens the asset and never during an automated cook.

**Why it is silent.** It is the correct default and it works — authors do get
feedback. Nothing degrades; the check simply is not present in the pipeline where
bad data would otherwise be caught.

**Why the obvious check misses it.** Searching for validation finds it, in
quantity, well written. The question that matters is narrower: *does any of it
run outside the editor?* — and answering that means reading preprocessor guards
rather than validation logic.

**Symptom.** Invalid data reaches a packaged build. The team's belief that "we
validate our data" is true and irrelevant.

**Detect.** Count validation entry points, then count the ones that survive a
non-editor build, then look for a runner:

```bash
rg -n "IsDataValid" --glob "*.h" . | wc -l
rg -n -B3 "IsDataValid" --glob "*.h" . | rg -c "WITH_EDITOR"
rg -n "Commandlet|AutomationTest|ValidateAssets" --glob "*.h" --glob "*.cs" .
```

In the audited reference this gave twelve entry points, **eleven** of them
editor-only, plus a content-validation commandlet and a validator base class —
so the mechanism to run them in automation exists and the question becomes
whether the pipeline invokes it.

**Guardrail.** Editor validation is feedback; a commandlet or automation test in
the build pipeline is the boundary. Ensure the runner **fails the build** on
error — a validator whose result is only printed is a log line, not a gate.

---

### DD-10 - The validator reports and the pipeline does not care

**Mechanism.** Validation runs in automation and prints errors. The process exit
status does not reflect them, so the pipeline continues.

**Why it is silent.** Everything works: the check runs, the errors are found, the
log contains them. The only missing link is the one nobody looks at until a bad
asset ships.

**Why the obvious check misses it.** Both halves are present and correct — there
is validation, and there is a pipeline step running it. The defect is in the
contract between them, which is a single integer nobody reads.

**Symptom.** A green build over a log full of validation errors. Confidence
inversely proportional to actual coverage.

**Detect.** Check what the runner returns and what the pipeline does with it:

```bash
rg -n -A20 "class UContentValidationCommandlet|int32 Main\(" --glob "*.h" --glob "*.cpp" . \
  | rg "return |ExitCode|GIsCriticalError"
rg -n "Commandlet" .github/ *.yml *.yaml 2>/dev/null
```

A commandlet whose `Main` returns zero unconditionally is the finding. Confirm by
deliberately breaking one asset and running the pipeline step: if it stays green,
the gate does not exist.

**Guardrail.** Prove the gate by breaking something on purpose. **A check that
has never failed is indistinguishable from a check that cannot fail** — this is
the same principle as the poisoned-fixture rule for any linter, applied to your
content pipeline.
