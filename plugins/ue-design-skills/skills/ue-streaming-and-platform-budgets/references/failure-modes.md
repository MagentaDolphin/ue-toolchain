# Failure modes: streaming and platform budgets

Ten ways a platform budget is configured, reviewed, approved and inert.

The shared property here is different from the rest of this bundle, and it is the
reason this file exists: **configuration cannot fail.** A line in an ini file
that names an unreachable section, a variable set at a priority nothing can
override, a clamp that compares two different units — none of these produce an
error, a warning, or a log line. They produce a game that runs, on hardware that
was budgeted for, using numbers nobody set.

A second property: **the instrument lies more often than the code.** Most wrong
conclusions in this area come from reading a pool setting as consumption, or a
scalability level as an outcome. Several recipes below check the instrument
rather than the project.

Recipes use `rg` from a project root and were executed against the audited
project while this file was written. Runtime recipes name the console command,
because static analysis genuinely cannot answer some of these.

---

## Priority and arbitration

### ST-01 - A value set at a priority nothing can override

**Mechanism.** A device profile sets a streaming variable. Device-profile
priority outranks scalability priority, so every later quality change — including
every in-game setting — is silently discarded for that variable.

**Why it is silent.** Both halves work exactly as designed. The profile applies
its value; the settings system applies its value; the higher priority wins and
nobody is told. The setting's UI shows the user's choice, which is stored
correctly and simply has no effect.

**Why the obvious check misses it.** Reading either file shows a sensible value.
Reading both shows two sensible values with no visible conflict, because priority
is not expressed in the files at all — it is a property of the mechanism that
applied them. And the same setting **does** work on a tier where the profile is
silent, so "it works on my device" is true and useless.

**Symptom.** A quality setting that works on some hardware and not on other
hardware, with no pattern the player or the tester can see.

**Detect.** Ask the running game who set the value — this cannot be done
statically:

```text
DumpCVars                    # every variable with its SetBy source
r.Streaming.PoolSize         # prints the value and its source
```

Then find the static side and compare coverage:

```bash
rg -n "r\.Streaming\.PoolSize" Config/
rg -n "^\[TextureQuality@" Config/ | wc -l
```

In the audited project the pool is set in exactly two places — the mid tier of
each mobile platform — and the project declares **no** per-tier texture-quality
sections at all, so every other tier inherits the engine's values. One setting,
opposite behaviour across tiers.

**Guardrail.** Document the intended source per quality variable, and assert it
in a startup dump on each platform. If a value must be immutable, say so in the
settings UI rather than accepting the write and dropping it.

---

### ST-02 - The top quality bucket detaches the pool from real memory

**Mechanism.** The highest quality buckets disable the clamp that limits the
streaming pool to available video memory, while automatic detection promotes
hardware into those buckets on a compute benchmark that never considers memory
size.

**Why it is silent.** Both decisions are defensible alone. Disabling the clamp on
the top bucket assumes a machine with plenty of memory; a compute benchmark is a
reasonable proxy for GPU class. The combination targets exactly the hardware the
assumption is wrong about: a fast chip with modest memory.

**Why the obvious check misses it.** The clamp lives in engine configuration and
the thresholds live in project configuration. Each is reviewed by a different
person, in a different file, at a different time. Neither file mentions the
other.

**Symptom.** Stutter and driver-level eviction on mid-range cards, at the quality
tier automatic detection chose for them. Reproduces on hardware the team does not
own, because the team's machines have enough memory for the assumption to hold.

**Detect.** Read the thresholds, then read what the top bucket does to the clamp:

```bash
rg -n "PerfIndexThresholds_TextureQuality" Config/
rg -n "LimitPoolSizeToVRAM|r\.Streaming\.PoolSize" \
  "<engine>/Engine/Config/BaseScalability.ini"
```

Confirm on hardware: set the quality level manually and watch the pool.

```text
sg.TextureQuality 3
stat streaming               # pool size, required pool, over budget
```

**Guardrail.** Include a memory term in the promotion thresholds, or keep the
clamp enabled on the top bucket. Test the top bucket on a low-memory card before
shipping the thresholds.

---

### ST-03 - Meshes and textures share a budget nobody split

**Mechanism.** Mesh streaming is enabled, and the separate mesh pool is left at
its default, which means one shared pool.

**Why it is silent.** Sharing is a supported configuration and works. Textures and
geometry simply compete inside one ceiling, and the streamer resolves the
competition by lowering mips — which looks like a texture problem.

**Why the obvious check misses it.** Two separate settings, one enabled in a
renderer section and one absent from every platform except mobile. Nothing
connects them, and the absent one has a default whose meaning ("share") is only
documented in the engine's variable description.

**Symptom.** Texture quality degrading on scenes with heavy geometry, on
platforms where nobody configured a mesh budget.

**Detect.** Check both values on every platform, and check where each was set:

```bash
rg -n "r\.MeshStreaming" Config/
rg -n "r\.Streaming\.PoolSizeForMeshes" Config/
```

In the audited project mesh streaming is enabled globally in the renderer
settings while the mesh pool is configured only for mobile — so desktop and
console share one pool by default.

**Guardrail.** Set both explicitly per platform, even when the value equals the
default. An explicit default is a decision; an absent one is an assumption.

---

### ST-04 - A read-only variable treated as a runtime knob

**Mechanism.** Several streaming variables are marked read-only: their value is
captured at startup and influences what is cooked. Setting them later — from a
console, a device profile, or a settings screen — is accepted and ignored.

**Why it is silent.** The write succeeds. Nothing rejects it, nothing warns, and
the variable reads back as unchanged, which is easy to miss when you are looking
at frame time rather than at the variable.

**Why the obvious check misses it.** The variable has a name, a value and a
description like any other. Its flags are in engine source, and nothing in the
project's configuration indicates the difference.

**Symptom.** An A/B comparison of a "setting" that produces two identical
configurations, and therefore a confident conclusion drawn from noise.

**Detect.** Check the flags before tuning anything:

```bash
rg -n -B2 -A6 "r\.MeshStreaming|CoarseMeshStreaming" \
  "<engine>/Engine/Source/Runtime/Engine/Private/ContentStreaming.cpp" \
  | rg "ECVF_ReadOnly|ECVF_Scalability"
```

At runtime, the same question is one command: print the variable and confirm the
value changed after you set it.

**Guardrail.** Maintain a short list of the build-level streaming decisions in
your project, next to the platform matrix. Anything on that list is changed in a
build, never in a session, and never compared mid-session.

---

## Reachability

### ST-05 - A profile section that nothing can select

**Mechanism.** A device profile section is defined with a full set of values, and
no registry entry or matching rule leads to it.

**Why it is silent.** The file parses, the section is well formed, and the values
inside it are correct. It is simply never chosen, so it produces no behaviour to
be wrong.

**Why the obvious check misses it.** Reviewers read sections, not the registry.
A tier section that sits beside three reachable siblings looks exactly like them
— same shape, same variables, same care — and the difference is a missing line in
a list at the top of the file, or an absent mapping in engine configuration.

**Symptom.** A platform that never reaches its top tier, with per-tier values
that were reviewed, approved and never applied.

**Detect.** Diff declared profiles against defined sections:

```bash
rg -n "DeviceProfileNameAndTypes" Config/DefaultDeviceProfiles.ini
rg -n "^\[\w+ DeviceProfile\]" Config/DefaultDeviceProfiles.ini
```

Every defined section must be either declared here or present in the engine's
base profiles. In the audited project one platform's top tier is defined in full
and appears in neither list — every value in it is unreachable.

Confirm on hardware, which is the only authoritative answer:

```text
dumpdeviceprofile            # the active profile and its variables
```

**Guardrail.** Assert reachability in a test that parses both lists. A profile
that cannot be selected should fail the build, not be discovered on a device.

---

### ST-06 - Section headers that contradict the assignment

**Mechanism.** Comment banners group device sections under tier labels. The
sections beneath name a different base profile.

**Why it is silent.** Comments do not execute. The devices get the tier their
base profile names, which is a real and consistent assignment — just not the one
the banner announces.

**Why the obvious check misses it.** The banner is the fastest way to read a
600-line configuration file, and it is the wrong instrument. Checking means
reading the base profile line of every device section, which is exactly the work
the banner appears to save.

**Symptom.** Device tier assumptions in planning documents that do not match
runtime. Performance reports grouped by a tier the devices are not in.

**Detect.** Ignore banners; extract the pairs:

```bash
rg -n -A2 "^\[\w+ DeviceProfile\]" Config/DefaultDeviceProfiles.ini \
  | rg "DeviceProfile\]|BaseProfileName"
```

Read the output as a table. In the audited project several devices sitting under
a high-tier banner resolve to the low tier.

**Guardrail.** Generate the device-to-tier table from configuration rather than
maintaining banners, and put the generated table in the performance
documentation.

---

### ST-07 - An override list that no configuration populates

**Mechanism.** A platform settings object declares a list of user-facing profile
variants. Selection logic composes a profile name from that list. No
configuration file ever sets it.

**Why it is silent.** The composition handles an empty list gracefully: the
resulting name is empty, no matching profile is found, and the override is not
applied. The engine's startup selection stays in effect, which is correct
behaviour and looks like intent.

**Why the obvious check misses it.** The code is complete and reads well —
fallback chains, refresh-rate filtering, logging. Confirming the absence means
searching every platform's configuration for a property that is never mentioned
in the source that consumes it.

**Symptom.** A console-style quality preset UI that never appears, because it is
only added when the variant list has more than one entry. The feature is
"implemented" and has never run.

**Detect.** Separate reads from writes:

```bash
P='UserFacingDeviceProfileOptions'
rg -n "\b$P\b" Source/ Config/ Platforms/
```

Hits only in a declaration and in read sites — with nothing in any configuration
file — is the finding. In the audited project the property is read in three
places and set in none.

**Guardrail.** For every data-driven selection list, add a startup log naming its
size, and treat zero as a warning. The logging line already exists in most such
systems; make someone read it.

---

## Configuration that cannot take effect

### ST-08 - Settings for a delivery mechanism the project does not have

**Mechanism.** Texture groups configure optional mip levels, which are cooked
into a separate chunk. The project has no chunk installation and does not acquire
missing chunks on load.

**Why it is silent.** The settings are valid, the cook honours them, and nothing
at runtime asks for the chunk that would contain the extra mips. Everything
behaves as if the settings were absent.

**Why the obvious check misses it.** The group configuration is reviewed as a
block of texture settings, where the value is plausible. The dependency on a
delivery mechanism is two systems away, in packaging configuration nobody reads
during a texture pass.

**Symptom.** A team believes it has a high-resolution optional tier. It does not,
and the belief survives because nothing contradicts it.

**Detect.** Check the consumer of the mechanism, not the producer:

```bash
rg -n "OptionalMaxLODSize|OptionalLODBias" Config/
rg -n "bShouldAcquireMissingChunksOnLoad|bBuildHttpChunkInstallData" Config/
```

Optional mips configured while chunk acquisition is disabled is the finding.

**Guardrail.** Configuration that depends on a delivery mechanism gets a comment
naming that mechanism, and a check in the packaging review. Better: remove it
until the mechanism exists.

---

## Clamps

### ST-09 - A clamp comparing two different units

**Mechanism.** A compatibility check obtains a **resolution percentage** and
compares it against a **quality level**. The percentage defaults to one hundred
and the level ranges to three, so the comparison is always satisfied.

**Why it is silent.** Both values are integers, both accessors exist, and the
comparison is well typed. The constraint simply never binds, which is
indistinguishable from a constraint that is never violated.

**Why the obvious check misses it.** The line reads correctly. The two accessor
names differ by one word, the sibling function two hundred lines away uses the
correct one, and nothing about either line suggests a unit mismatch. This is a
type error that the type system cannot express.

**Symptom.** A frame-rate and quality compatibility rule that never fires, so a
platform can select a combination the rule exists to prevent.

**Detect.** Find clamps and check the accessor against the value being compared:

```bash
rg -n -B4 -A4 "GetApplicable\w*Limit\(" Source/ | rg "Quality|Resolution|Limit"
```

Read each hit for unit agreement. Then unit-test every clamp at both ends of its
real range — the test that would have caught this takes three lines.

**Guardrail.** Give the two ranges distinct types, or name the accessors so a
mismatch is visible in one line. Test each clamp with a value that must be
rejected; a clamp with no failing test case has never been shown to work.

---

### ST-10 - A remap with a reachable zero denominator

**Mechanism.** A normalisation maps a value between two ranges by dividing by the
difference between a maximum and a minimum. Nothing guarantees they differ.

**Why it is silent.** For every configuration anyone has tried, they differ. The
division is correct and the result is correct.

**Why the obvious check misses it.** The formula is standard and reads as
obviously right. Reachability of the degenerate case depends on data — a device
profile setting a limit equal to the scale minimum — and data is not reviewed with
the arithmetic.

**Symptom.** An infinity or a not-a-number propagating into a quality value on
one device configuration, producing behaviour that is hard to attribute and
impossible to reproduce elsewhere.

**Detect.** Find range normalisations and check their guards:

```bash
rg -n -B3 -A1 "\) / \(\w+ - \w+\)|/ \(Max\w+ - Min\w+\)" Source/
```

Any division by a difference with no preceding equality check is the finding.

**Guardrail.** Guard the denominator and decide the degenerate result
deliberately. Then check whether data can actually produce it — and if it can,
validate the data too.
