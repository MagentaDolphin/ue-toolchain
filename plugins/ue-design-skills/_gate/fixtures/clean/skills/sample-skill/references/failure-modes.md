# Failure modes: sample skill

Gate fixture. One complete entry, in the exact shape the gate accepts.

An entry is valid only if a reader who has never seen the donor project can run
`Detect` in their own tree and get an answer. The three middle fields are the
ones that cannot be written by someone who did not do the work.

---

### SS-01 - Editable property with no writer

**Mechanism.** A tunable float is compared against a timestamp field, but the
timestamp is never assigned anywhere in the codebase.

**Why it is silent.** Time since an unset stamp is time since world start, which
always exceeds the threshold. The comparison is permanently true, so the gate it
was meant to impose never rejects anything and no error is ever raised.

**Why the obvious check misses it.** The field is read twice and participates in
a comparison, so any "is this used?" search answers yes. What is absent is the
**writer**, not the reader.

**Symptom.** A designer tunes the property for days and reports that it changes
nothing.

**Detect.** For each editable property, search for an assignment rather than a
mention, and subtract the declaration -- a member declared with an initializer
matches every assignment pattern you can write:

    rg -n "\bPropertyName\b\s*(=|\+=|-=)" Source/ \
      | rg -v "\b(bool|u?int\d+|float|double|F[A-Z]\w+)\s+PropertyName\b"

If reads exist and this comes back empty, the property is a stub.

**Guardrail.** Do not ship an editor-exposed property whose value has no writer.
Every tunable needs one owning assignment site and one test that moves it.
