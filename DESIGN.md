# Design notes

The written section the task asks for: the SHACL/JSON-LD modelling choices, how the translation
to a frontend form schema works, and the limitations and assumptions I accepted.

---

## 1. What is the source of truth, exactly

The brief says the backend should drive form logic from JSON-LD documents and SHACL shapes. The
sharpest version of that idea is that **one artefact is authored and three are derived**, so
there is no second place for them to disagree:

```
                          ┌─→ JSON Schema      (what controls to render)
sh:PropertyShape ─────────┼─→ JSON Forms UI    (how to lay them out)
                          └─→ JSON-LD @context (how to read the answer back)
```

A single pass over the property shapes produces all three (`shacl/jsonforms.py`). The JSON key
for a field is chosen once, from `sh:name`, and is therefore identical in the form the browser
renders, in the context that lifts the submission into RDF, and in the JSON pointer that reports
a violation. The same map is used in reverse in `shacl/report.py`, which is what keeps error
reporting from drifting away from form generation.

The corollary matters as much: **the generated JSON Schema is a rendering hint, not a security
boundary.** It cannot express the `sh:sparql` cross-field rules, so a payload that satisfies it
can still be rejected. The server never consults it. SHACL is the authority.

### Two halves of the model

| File | Holds | Why there |
|---|---|---|
| `data/vocab/food.ttl` | terms, `rdfs:label`, `food:surcharge`, allergens, diet exclusions | An option is described **once**; every dish offering it inherits the label and the price |
| `data/shapes/common.ttl` | property shapes every dish reuses (`quantity`, `customerName`, …) | Reused by IRI, so "every dish asks for a name the same way" is a fact, not a convention |
| `data/dishes/<slug>/shape.ttl` | that dish's `sh:NodeShape` | Constraints are per-dish; nothing else is |
| `data/dishes/<slug>/dish.jsonld` | catalogue entry: name, price, tags, allergens | Presentation data with no constraints attached |

Pricing reads `food:surcharge` off the same vocabulary terms the form offers, so a new option's
price is set where the option is defined rather than in a lookup table someone has to remember.

### Option values are IRIs, not strings

Enumerated options travel the wire as plain tokens (`"veganMiso"`) but land in the graph as real
IRIs (`food:veganMiso`). The generated context does this with `"@type": "@vocab"`.

This is the choice that makes the rest work. Because an option is a node, the SPARQL rules can
ask questions *about* it — `?value food:excludedByDiet "vegan"` — instead of matching strings.
The ramen rule therefore never lists a topping: annotate a new topping as non-vegan in
`food.ttl` and it falls under the existing constraint with no rule change.

### Shapes are closed

`sh:closed true` turns RDF's open-world default off, so an unknown field is a violation rather
than silently ignored. A form that accepts `{"secretDiscount": "free"}` without complaint is
not validating anything. `sh:ignoredProperties` exempts `rdf:type` and `food:dish`, both of
which the *server* sets — a client cannot smuggle in a different dish by putting one in the body.

### Meaningful constraints, not decorative ones

Every dish exercises cardinality (`1..2` meats, `0..5` toppings), enumeration, datatypes,
numeric ranges, string length and pattern, defaults, grouping, closure — and one `sh:sparql`
cross-field rule that no JSON Schema could express:

| Dish | Rule |
|---|---|
| French Tacos | Two meats only fit an XL tortilla |
| Ramen | A vegan broth rules out any topping annotated `food:excludedByDiet "vegan"` |
| Poke Bowl | A bowl whose proteins are all plant-based cannot take a non-vegan dressing |

---

## 2. The translation

`shacl/introspect.py` reads a node shape into plain dataclasses; nothing downstream touches an
rdflib graph. `shacl/jsonforms.py` turns those into the three artefacts.

| SHACL | JSON Schema | UI Schema |
|---|---|---|
| `sh:path` + `sh:name` | property key | `scope: #/properties/<key>` |
| `rdfs:label` | `title` | control `label` |
| `sh:datatype` | `type`, `format` | control kind |
| `sh:minCount ≥ 1` | entry in `required` | — |
| `sh:maxCount > 1` or absent | `array` + `minItems`/`maxItems`/`uniqueItems` | multi-value control |
| `sh:in` | `oneOf: [{const, title}]`, titles from `rdfs:label` | radio if ≤ 3 options, else select |
| `sh:minInclusive` / `sh:maxInclusive` | `minimum` / `maximum` | slider for narrow integer ranges |
| `sh:minLength` / `sh:maxLength` / `sh:pattern` | same | `multi` when `maxLength ≥ 120` |
| `sh:defaultValue` | `default` | — |
| `sh:description` | `description` | — |
| `sh:message` | — | control hint |
| `sh:group` → `sh:PropertyGroup` | — | `Group`, ordered by the group's `sh:order` |
| `sh:closed true` | `additionalProperties: false` | — |
| `sh:sparql` | **inexpressible** | server-side only |

`oneOf` with `const`/`title` rather than a bare `enum`, because it is the only draft-07
construct JSON Forms renders with human labels — which is what lets an option be labelled once
in the vocabulary and inherited by every dish.

Layout comes from `sh:group`, which SHACL provides natively for exactly this purpose, so the
form's structure is modelled data rather than a convention invented here.

### Errors carry JSON pointers

A violation is only useful if it lands on the control that caused it. pySHACL returns a report
graph; `shacl/report.py` turns each result into:

```json
{
  "pointer": "/toppings/1",
  "field": "toppings",
  "path": "https://sdsc.example/ns/food#topping",
  "constraint": "SPARQLConstraintComponent",
  "severity": "violation",
  "message": "Chashu pork is not available with a vegan broth.",
  "value": "chashu"
}
```

For an array the pointer addresses the **offending element**, recovered by matching `sh:value`
against the submitted payload. On the client the mapping to JSON Forms is then the identity
function: Ajv addresses errors by `instancePath`, which is also a JSON pointer.

### An empty field is absent, not empty

Worth stating because it bites: `sh:datatype xsd:dateTime` rejects `""`, so a cleared optional
field must send *no key at all* rather than an empty string. The renderers set `undefined`
rather than `''`, and `POST /api/orders/ramen` with `"pickupTime": ""` returns a 422 that says
so — which is the behaviour the control is built around, not one it works around.

---

## 3. Languages

Every form is served in the four Swiss national languages and English: German, French, Italian,
**Romansh**, English. Romansh is included because in this design a language costs one file, so
omitting it would have been a decision rather than a constraint.

### Adding a language is adding one file

```
backend/src/food_api/data/i18n/<lang>.ttl
```

It declares nothing. Every subject in it already exists in the vocabulary, the shared property
shapes or a dish shape; the file only attaches language-tagged literals to them:

```turtle
food:RamenBrothProperty
    rdfs:label "Brühe"@de ;
    sh:description "Die Basis der Schale. Tonkotsu köchelt achtzehn Stunden."@de ;
    sh:message "Wähle genau eine Brühe."@de .
```

This is why the dish property shapes and cross-field constraints are **named** rather than
inline blank nodes: a translation file needs something to attach to. That change cost some
verbosity in the shape files and bought a translation model with no code in it at all.

### Only what differs is translated

The fallback chain in `introspect.select_literal` is: exact tag → same language ignoring region
(`de-CH` → `de`) → English → untagged → anything. So "Nori" and "Ponzu" carry **one** untagged
label rather than five identical ones, and a German request still resolves them. A half-finished
translation degrades to English word by word instead of failing.

### The invariant: translation changes only what people read

| Varies with language | Identical in every language |
|---|---|
| `title`, `description`, control hints | JSON keys (`sh:name`) |
| Option labels | Option values (`veganMiso`) |
| Violation messages | Constraints, defaults, cardinality |
| Dish name, description, cuisine | The JSON-LD `@context` |
| | JSON pointers in violations |
| | The price |

A form rendered in Romansh is validated and priced by the English one, and a client may switch
language between rendering a form and submitting it without re-mapping anything.
`tests/contract/test_every_language.py` asserts exactly this, parametrised over the corpus - plus
a guard that the corpus has not silently degraded to English everywhere, since every other test
there checks *consistency*, which a monolingual corpus would satisfy perfectly.

Negotiation is `?lang=` first (a deliberate click should beat browser configuration), then
`Accept-Language`, then English. An unsupported language is not a 400 - asking for Spanish is
just something this menu does not have.

### What is not translated from the corpus

Two things, both deliberate:

- **The UI chrome** - buttons, headings, the empty state - lives in `frontend/src/i18n.ts`.
  It is client vocabulary, not dish vocabulary. Putting dish words there would rebuild exactly
  the coupling this project exists to remove.
- **One backend string**: the `sh:closed` message. pySHACL generates it, there is no
  `sh:message` behind it to translate, and its generated text names the internal order IRI. It
  is the single exception to "messages come from the shapes", and `report.py` says so.

---

## 4. Adding a dish

Two files, no code:

```
backend/src/food_api/data/dishes/<slug>/dish.jsonld
backend/src/food_api/data/dishes/<slug>/shape.ttl
```

The filesystem is the registry — there is no dish list in Python, no enum, no route per dish.
Commit [`7cf2f2f`](../../commit/7cf2f2f) adds Poke Bowl and its `git show --stat` is two data
files, nothing else. The contract suite in `backend/tests/contract/` parametrises over whatever
is on disk, so that dish inherited 13 tests without a line of test code being written for it.

The same commit is why the third dish is worth having: its shape exercises a required
multi-valued property with a lower bound above zero, and a cross-field rule keyed on a *count*
of annotated values rather than on one field's value. Neither appears in the first two dishes,
so it is evidence the translator generalises rather than having been fitted to them.

---

## 5. Where Meilisearch fits

Not in the brief; added because dish discovery is the natural next question and because it
strengthens the central claim rather than sitting beside it. Search documents are projected
from the loaded catalogue, including option labels pulled out of the shapes — so a new dish
becomes searchable, by name and by anything it merely *offers*, with no indexing rule written
for it. `GET /api/search?q=cashew` returns the poke bowl.

It sits behind a `SearchPort` protocol. The API and unit suites run against an in-memory fake
and need no container; a real outage degrades `/api/search` to a 503 problem document and
leaves forms and ordering working, which `/healthz` reports as `degraded` rather than down.
Anything depending on real relevance — typo tolerance, filter syntax, index settings — is
covered by integration tests against a live instance, which CI runs as a service container.

---

## 6. Things I found by running, not assuming

Recording these because each was a silent failure, and the second one is the dangerous kind.

**pySHACL's `ont_graph` is invisible to SPARQL constraints.** The vocabulary has to be merged
into the *data* graph. Passing it as `ont_graph` produces a graph where `?value
food:excludedByDiet "vegan"` never matches, so every cross-field rule silently passes — a
validator that reports "valid" for everything. There is no error, no warning; only a test that
asserts a *rejection* catches it.

**A SPARQL constraint needs `?path` bound in its `SELECT`** to produce a `sh:resultPath`, and
without one the violation has no JSON pointer and floats free of the form.

**`sh:pattern` is compiled with Python's `re`.** SHACL specifies XPath regexes, which have
`\p{L}`; Python does not. A "letters only" name pattern raises at shape-load time. The name
constraint therefore checks *shape* — no leading/trailing whitespace — not alphabet, which is
also the more inclusive choice.

**`sh:closed` messages are built in the report layer**, not with an `sh:message` on the node
shape: SHACL applies a node shape's message to *every* constraint it carries, so declaring one
there appends "unknown field" to unrelated violations. pySHACL's default text also names the
internal order IRI, which no client should see.

**eslint hoists ajv 6 while JSON Forms runs ajv 8**, so `ErrorObject` type-checked against the
wrong shape (`dataPath` rather than `instancePath`). ajv 8 is now an explicit dependency,
matching what actually executes.

**pySHACL strips the language tag from `sh:sparql` messages** while preserving it for core
constraints — it runs template substitution and rebuilds the literal, losing the tag. All five
translations therefore arrived indistinguishable and were concatenated into one sentence.
`report.py` follows `sh:sourceConstraint` back to the shapes graph and selects the tagged
literal there instead. The regression test asserts no message exceeds 200 characters, which a
five-way concatenation comfortably does.

**Message templating and multilingual labels do not mix.** The ramen rule once interpolated
`{$optionLabel}` into its message. Once the term carried a label in five languages the query
bound whichever it reached first, unpredictably. The interpolation is gone: the JSON pointer
already addresses the exact array element, so naming it in prose was redundant anyway.

---

## 7. Limitations and assumptions

**`sh:name` is read as a field identifier.** The SHACL spec intends it as a human-readable
label. A form needs one stable token that is at once the JSON key, the JSON-LD term and the
error pointer, and `sh:name` is the only per-property naming slot SHACL offers. `rdfs:label`
supplies the display title instead. This is a deliberate deviation and the one thing in the
model I would most want to discuss.

**Only simple IRI paths.** Sequence, alternative and inverse `sh:path`s have no flat JSON
equivalent, so the translator rejects them at load time rather than dropping the field. Nested
objects would mean nested JSON Schema and a recursive translator — a real extension, not a
patch.

**Cross-field rules cannot reach the client before submission.** JSON Forms has a `rule`
mechanism that could express *some* of them (show/hide, enable/disable), but not
`FILTER NOT EXISTS` over vocabulary annotations. Today they are enforced only on submit. The
honest framing: the client gets fast feedback on what JSON Schema can express, and the server
is the authority on everything.

**Errors accumulate rather than replace.** A field showing a server violation also shows Ajv's
own optimistic message, and the vanilla renderers concatenate them. Distinguishable
programmatically (`keyword: 'shacl'`), not visually.

**Icons are SVG, not Unicode glyphs.** `☀` (U+2600) has an emoji presentation, so Windows and
Chrome render it through Segoe UI Emoji as a full-colour **orange** sun — a colour from nowhere
sitting in a masthead built on SDSC indigo. A variation selector only asks nicely; inline SVG
drawing with `currentColor` is the only way to guarantee an icon takes the theme's colour.

**Text on the accent is a token, not `#fff`.** In dark mode the accent is a *light* indigo,
where white text measures **2.87:1** and fails WCAG AA. `--on-accent` is white in light mode and
dark navy in dark mode, which measures 6.41:1. Hardcoding white was the kind of mistake that
only shows up when you compute the ratio.

**Client-side validation is switched off entirely.** JSON Forms' `validationMode` is
`NoValidation`, and only the server's violations are displayed. This follows from SHACL being
the authority, and it fixes two things at once: Ajv was marking every required field red on
first render, before the user had typed anything, and labelling them with untranslated English
("is a required property") inside a UI that is otherwise localised into five languages.
`additionalErrors` are unaffected by that mode, so the server's messages still land on their
controls.

**The summary duplicates the price, on purpose.** It shows the total beside the form *and* a
compact problem count, while the form itself carries the full violation notice. Two places
saying the same thing is usually a smell; here the summary is sticky and the notice is not, so
the alternative is a total that scrolls out of view while someone is still customising. The two
strings are deliberately different (`{n} to fix` vs the full sentence) so they read as one
system rather than as an echo.

**The price shown while customising is an estimate.** It is computed in the browser from the
`pricing` block, and the server recomputes it authoritatively on submit. They agree today
because both read the same `food:surcharge` annotations, but the receipt is the number that
counts and the UI says so.

**The custom renderers are heuristics, and heuristics have edges.** Five of them
(`frontend/src/renderers/`) match on the *shape* of a schema, never on a field name: an array
of enumerated values becomes chips, a short enumeration becomes cards, a bounded integer becomes
a stepper or a slider, and a `format: date-time` string becomes a date picker with a **Now**
button so nobody has to type an ISO timestamp. The slider/stepper split turns on whether the minimum is zero — a scale
starts at zero, a count starts at one — which is a real signal but not a guaranteed one. A shape
that violated it would get the wrong-but-usable control. Making that explicit would mean a
`food:` annotation for control intent, which starts down the road of putting presentation in the
vocabulary.

**No persistence, no auth, no rate limiting.** The brief asks for none, and an order that is
priced rather than stored keeps the demo honest about what it does. The order IRI is minted per
request and is unique only within that request.

**Romansh is machine-translated and unreviewed.** The four national languages are all served,
but a Rumantsch Grischun speaker should read `data/i18n/rm.ttl` before this is shown to anyone
as finished. The other three I can vouch for; that one is flagged in the file itself and in
`AI_USAGE.md`. Coverage there is also deliberately partial — field labels, group labels and
validation messages, with proper nouns falling through the chain.

**Language is negotiated but not routed.** There is no `/de/…` URL prefix and no
`Vary: Accept-Language` on cached responses, so a shared cache in front of this API would need
configuring before it could serve two languages correctly. Fine for a prototype, wrong for
production.

**Meilisearch relevance is untuned.** Default ranking rules, no synonyms, no stop words. Enough
to demonstrate the projection; not tuned for a real menu.

---

## 8. What I would do next, in order

1. **Have a Romansh speaker review `data/i18n/rm.ttl`**, and complete the option-label coverage
   in all four languages. The mechanism is finished; the content is not.
2. **Emit JSON Forms `rule`s for the expressible subset of cross-field constraints**, so
   `sh:sparql` rules that reduce to "hide X when Y" give feedback before submit. The rest stay
   server-only and the write-up says which.
3. **Persist orders**, which turns the receipt into a resource and makes the order IRI mean
   something.
4. **Generate a TypeScript client from the OpenAPI document** so `api.ts` cannot drift from the
   server contract.
5. **Property-based tests over generated shapes** (hypothesis), asserting the invariant that
   *anything SHACL accepts, the generated schema accepts* — currently checked only against
   hand-written fixtures.
6. **Serve the vocabulary and shapes as content-negotiated linked data**, so the IRIs in the
   generated context dereference. They are `sdsc.example` placeholders today.
