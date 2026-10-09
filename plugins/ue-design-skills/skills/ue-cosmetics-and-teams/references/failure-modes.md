# Failure modes: cosmetics and teams

Eleven ways an appearance system or a team system produces the wrong result
without producing an error.

The shared property differs slightly between the two halves, and both are worth
stating.

**Cosmetics fail by looking almost right.** A wrong mesh, a missing part or a
duplicated accessory is a visual outcome, and every visual outcome is plausible
to code. Nothing can assert that a character looks correct, so these defects are
found by people, late, and reported as "the skin is broken".

**Teams fail by permitting.** Every interesting team defect resolves to
"indeterminate", and the branch that handles indeterminate almost always allows
the action, because denying it would have blocked something during development.

Recipes use `rg` from a project source root and were executed against the audited
project while this file was written.

---

## Cosmetics

### CT-01 - The isolation guarantee is one line, and it is narrower than it looks

**Mechanism.** Cosmetic presentation is excluded from the dedicated server by a
single net-mode check at the spawn site. That check is the entire reason cosmetic
content cannot influence authoritative simulation.

**Why it is silent.** It works. On a dedicated server no presentation actor
exists, so none can collide, block a trace or tick. The guarantee holds exactly
where it is claimed.

**Why the obvious check misses it.** The guarantee is usually restated as
"cosmetics cannot affect gameplay", which is a stronger claim than the code
makes. On a listen server or in standalone the parts **do** exist on the
authority, with whatever collision and components their class carries. Nothing in
the type system prevents a part class from containing an ability system or
enabled collision — the constraint is content discipline plus one `if`.

**Symptom.** A cosmetic accessory that blocks a shot, or a part actor that ticks
expensively, in exactly the configuration used for local playtesting — and never
on the dedicated server where the "real" testing happens.

**Detect.** Find the guard, confirm there is only one, and check what part
classes are permitted to contain:

```bash
rg -n "NM_DedicatedServer|IsNetMode" --glob "*.cpp" <cosmetics-module>/
rg -n "CollisionMode|SetActorEnableCollision" --glob "*.cpp" --glob "*.h" \
  <cosmetics-module>/
```

In the audited project the first command returns **exactly one line** for the
whole module. That is elegant and it is also the entire safety boundary, which is
worth knowing before relying on it.

**Guardrail.** State the guarantee accurately: "not present on a dedicated
server", not "cannot affect gameplay". Validate part classes at author time —
reject any that contain an ability system component, replicated properties or
enabled collision by default.

---

### CT-02 - Every change rebuilds the actor

**Mechanism.** The replication callback for a changed entry destroys the spawned
presentation and spawns a new one, because propagating a diff into a live actor
is hard and rarely needed.

**Why it is silent.** It is correct. The result after a change is exactly the
result after an add, which is what the system promises. The cost is a rebuild,
and a rebuild looks identical to a first build.

**Why the obvious check misses it.** The implementation is deliberate and
commented as such. Reviewing it shows a decision, not a defect. The consequence
only appears at a usage frequency nobody has yet — a system that changes parts
rarely and one that changes them per second are the same code.

**Symptom.** A hitch on every cosmetic edit. Discovered when a feature starts
mutating parts at runtime — a preview screen, a colour cycler, a progression
system — long after the mechanism was reviewed.

**Detect.** Read what the change callback does, and compare it with the add path:

```bash
rg -n -A12 "PostReplicatedChange" --glob "*.cpp" . | rg -i "destroy|spawn|update"
```

If change is implemented as destroy plus spawn, treat the mechanism as
add/remove only and design callers accordingly.

**Guardrail.** Document the cost where authors will see it. If frequent edits are
planned, add a real update path for the fields that can change in place, and keep
the rebuild for the ones that cannot.

---

### CT-03 - Rule order is priority, and nothing says so

**Mechanism.** A selection set is an array of rules, each with a set of required
tags, plus a default. The first rule whose tags are all present wins. Rules are
not sorted by specificity.

**Why it is silent.** Every possible input produces a result — either a rule or
the default. There is no "no match" state to report, and the result is always a
valid asset.

**Why the obvious check misses it.** The array looks like a set, and sets have no
order. A reviewer checking "are the rules correct?" checks each rule in
isolation, where each is correct. The defect exists only in the relationship
between a broad rule and a narrower one below it, which requires comparing every
pair.

**Symptom.** A character with a specific tag combination gets the generic mesh.
Nobody notices for weeks, because it is the *right kind* of mesh.

**Detect.** Find selection sets and check for shadowing — a rule whose tag set is
a subset of an earlier rule's:

```bash
rg -n -B2 -A6 "SelectBest|RequiredTags" --glob "*.h" --glob "*.cpp" .
```

Then, for each set, verify the shadowing property in a test rather than by
reading: for every pair of rules `i < j`, assert that rule `i`'s tags are not a
subset of rule `j`'s.

**Guardrail.** Write the ordering rule as a comment on the array and enforce the
subset check in validation. A rule that can never win is a content bug the
compiler cannot see.

---

### CT-04 - The realization path re-applies unconditionally

**Mechanism.** Recomputing appearance sets the mesh on every change broadcast,
relying on the setter to be cheap when the value has not changed — while passing
a flag that forces a pose reinitialization.

**Why it is silent.** The result is correct. The mesh is right, the pose is
right, and the cost is invisible at the frequency the system is normally used.

**Why the obvious check misses it.** The code carries a comment explaining that
the setter is a no-op when the mesh is unchanged, which answers the question a
reviewer would ask. The forced flag is a separate argument on the same call, and
it is not what the comment is about.

**Symptom.** A visible pose pop or an animation reset whenever anything about
cosmetics changes, including changes that do not affect the mesh at all.

**Detect.** Check the arguments of the re-application call, not just the call:

```bash
rg -n -B6 "SetSkeletalMesh\(" --glob "*.cpp" . | rg "bReinit|true|Broadcast"
```

A hardcoded reinitialization flag on a path that runs on every change is the
finding.

**Guardrail.** Compare before applying, and pass the reinitialization flag only
when the mesh actually changed. Idempotent realization means "applying twice
costs nothing", not merely "applying twice is correct".

---

### CT-05 - Everything is a hard reference

**Mechanism.** Part classes and selection-set assets are hard references, so the
entire cosmetic catalogue is loaded with whatever holds the rules.

**Why it is silent.** Hard references always resolve. Nothing is ever missing,
nothing ever fails to load, and every asset is available the moment it is needed.

**Why the obvious check misses it.** Reference correctness is what reviews check,
and hard references are maximally correct. The cost is memory residency, which
belongs to a different discipline and a different person, and which does not
appear in any test of the cosmetics system.

**Symptom.** Memory proportional to the size of the cosmetic catalogue rather
than to what is worn, discovered during a platform memory pass and attributed to
content rather than to a reference-type decision.

**Detect.** Count hard versus soft references in the cosmetic data types:

```bash
rg -n "TSubclassOf<|TObjectPtr<" --glob "*.h" <cosmetics-module>/ | wc -l
rg -n "TSoftClassPtr<|TSoftObjectPtr<" --glob "*.h" <cosmetics-module>/ | wc -l
```

A large first number with a zero second is the finding. See
`ue-asset-loading-and-memory` for what this costs and how to measure it.

**Guardrail.** Cosmetic catalogues are the textbook case for soft references and
bundles: large, optional, and mostly unworn. Decide per field and record the
decision in metadata.

---

## Teams

### CT-06 - The mirror setter that silently does nothing

**Mechanism.** Team identity is authoritative on one object and mirrored on
several others. The mirrors implement the interface's setter because they must,
and the implementation does nothing.

**Why it is silent.** Doing nothing is correct — the mirror is not the owner. The
call succeeds, returns, and the value is unchanged.

**Why the obvious check misses it.** The setter exists and is implemented. Any
review asking "does this type support setting a team?" answers yes. The caller
has no return value to check and no reason to suspect the write did not land.

**Symptom.** Code that sets a team on a controller or a pawn and observes the old
value. The investigation goes to replication, then to ordering, then eventually to
the setter.

**Detect.** Read the bodies of every team setter and classify them:

```bash
rg -n -A4 "::SetGenericTeamId|::SetTeamId" --glob "*.cpp" . \
  | rg -B1 "UE_LOG|ensure|^\s*\}"
```

The audited project does this **correctly** and is worth copying: the mirror
setters log an error naming the real owner rather than returning quietly. That
one line converts an invisible failure into a searchable one.

**Guardrail.** A mirror's setter logs an error identifying the authoritative
owner. Never implement a no-op setter to satisfy an interface.

---

### CT-07 - The header promises a policy the body does not implement

**Mechanism.** The damage-permission function is documented as taking friendly
fire settings into account. The body contains no settings and no lookup.

**Why it is silent.** The behaviour is coherent — allies are always safe — and
that is the right default for most modes. Nothing malfunctions.

**Why the obvious check misses it.** The comment *is* the documentation. A team
adopting the system reads the header, concludes friendly fire is supported, and
plans a mode around it. Discovering otherwise requires reading a body that looks
finished.

**Symptom.** A mode that needs friendly fire is scoped as a configuration change
and turns out to be a design change, in a function every damage path depends on.

**Detect.** Compare the promise with the implementation:

```bash
rg -n -i "friendly fire" --glob "*.h" --glob "*.cpp" .
rg -n -i "bFriendlyFire|bAllowFriendly|FriendlyFireSetting" --glob "*.h" --glob "*.cpp" .
```

In the audited project the first command finds the promise in a header comment
and the second returns **zero results project-wide**. A promise with no
implementing symbol is the finding, and this recipe generalises to any header
comment describing configurability.

**Guardrail.** Treat a comment describing behaviour as a claim requiring a
symbol. If the setting does not exist, the comment describes a plan and must say
so.

---

### CT-08 - Indeterminate resolves to permitted

**Mechanism.** Team comparison correctly returns three states. The damage rule
treats the indeterminate case as allowed when the target satisfies an unrelated
condition — in the audited project, having an ability system component.

**Why it is silent.** It exists to make something work: an unassigned training
target must be damageable. It succeeds at that, and the permissive branch is
never reached by any assigned actor during normal play.

**Why the obvious check misses it.** The function has three branches and handles
all three, so it passes any review asking whether the indeterminate case is
handled. It *is* handled — permissively — and the marker in the code says
"temporary".

**Symptom.** Any actor with an ability system and no team assignment is damageable
by anyone. Harmless while the only such actor is a target dummy; a rule violation
the moment a neutral faction, a destructible objective or an NPC exists.

**Detect.** Find every consumer of the relationship enum and read its
indeterminate branch:

```bash
rg -n -B4 -A10 "InvalidArgument|Indeterminate|NoTeam" --glob "*.cpp" . \
  | rg "return true|= true|Allow"
rg -n -i "//\s*@?TODO.*(temporary|until)" --glob "*.cpp" .
```

The second command is the high-yield one: a permissive branch that its own author
marked temporary is the strongest possible confirmation that the finding is real
and known.

**Guardrail.** Failure to determine must deny. Give the target dummy a team
instead of giving every unassigned actor an exemption — solve the specific
problem in data, not the general rule in code.

---

### CT-09 - A colour conversion that drops alpha

**Mechanism.** A four-channel colour is converted to a three-element vector to be
passed as a material parameter. The fourth channel is discarded.

**Why it is silent.** Three of four channels arrive correctly, so the colour is
right. Alpha is frequently unused in team colours, making the loss invisible for
as long as nobody encodes anything in it.

**Why the obvious check misses it.** The conversion is one token inside an
otherwise correct call. Both types are colours, both are correct, and the review
question — "is the parameter set?" — is answered yes.

**Symptom.** A team parameter that encodes opacity or a blend factor silently
reads as its default. In the same file, the effects-system path preserves all four
channels, so the same asset behaves differently in two places.

**Detect.** Find lossy conversions at parameter-setting sites:

```bash
rg -n "SetVectorParameterValue\w*\(.*FVector\(" --glob "*.cpp" .
rg -n "SetVariableLinearColor|SetVectorParameterValue" --glob "*.cpp" .
```

Two applicators for the same data with different channel counts is the finding.
In the audited project the material paths convert and the effects path does not.

**Guardrail.** Pass four channels where the API accepts them. If a conversion is
unavoidable, assert or document that alpha is unused.

---

### CT-10 - An accepted parameter that is ignored

**Mechanism.** The display-asset accessor takes a viewer identity so that
presentation can be relative — "my team always looks blue". The implementation
does not read it.

**Why it is silent.** The function returns the correct absolute asset. Every
caller gets a valid result, and the feature the parameter implies has simply
never been exercised.

**Why the obvious check misses it.** The signature and the header comment
describe the feature completely. Confirming absence requires reading the body,
where the parameter is unused — and an unused parameter produces no warning
because it is part of a virtual-looking public API.

**Symptom.** A team implementing viewer-relative colours writes correct calling
code and observes absolute colours. The bug appears to be in their code.

**Detect.** For any parameter that names a feature, check that the body reads it:

```bash
P='ViewerTeamId'
rg -n "\b$P\b" --glob "*.h" --glob "*.cpp" .
```

Occurrences only in the declaration and the definition's signature — with none in
the body — is the finding. In the audited project the body carries a comment
stating the parameter is currently ignored, which is honest and still ships an
API that cannot do what it claims.

**Guardrail.** Do not accept a parameter you do not use. Remove it, or implement
it, or make the function name state the limitation. This is the same defect class
as an ordering field that never sorts — see `ue-ui-architecture`, UI-01.

---

### CT-11 - "Private" that is not filtered

**Mechanism.** Team data is split into a public and a private actor to express a
replication boundary. The private one has no filtering; it is an empty subclass
with a note that privacy is not implemented.

**Why it is silent.** Everything works. Both actors replicate, both carry their
data, and the split is structurally correct — it is only the *filtering* that is
absent.

**Why the obvious check misses it.** The architecture is visible and right: two
types, two names, a clear intent. Reading the class names answers the question.
Confirming means noticing that the private subclass has no body.

**Symptom.** Data placed in the private actor because it is private is replicated
to every client. Nothing indicates this until someone inspects network traffic —
or until a competitor does.

**Detect.** Check that the privacy-named type actually filters:

```bash
rg -n -A15 "class \w*PrivateInfo|class \w*Private\w*" --glob "*.h" .
rg -n "IsNetRelevantFor|GetLifetimeReplicatedProps|COND_" --glob "*.cpp" . \
  | rg -i "private"
```

An empty subclass, or one with no relevancy or condition logic, is the finding.

**Guardrail.** A name is not a mechanism. Either implement the filtering — via
relevancy, replication conditions or a replication graph — or rename the type to
what it is. In the meantime, do not put anything in it that matters.
