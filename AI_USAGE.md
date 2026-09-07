# AI usage disclaimer

The task brief makes this disclaimer mandatory and asks it to separate **human-owned** work from
**AI-generated, non-owned** work.

**All code in this repository was written by Claude Opus 5, driven through Claude Code.** That is
the authorship answer and it does not vary by file. I chose the task and the stack, made the
scope decisions, and reviewed the result. The sections below say which parts I have read closely
enough to explain, modify and defend — which is the distinction the brief actually draws, since
it counts AI-assisted code as mine only to that depth.

---

## What I own

I can explain each of these decisions, argue the alternative I rejected, and change the code that
implements it.

- **The source of truth.** Shapes and JSON-LD documents are the only place a dish is defined;
  the JSON Schema, UI schema, context, price map and error pointers are all derived in one pass.
  The corollary matters more than the claim: the generated JSON Schema is a *rendering hint, not
  a security boundary* — it cannot express the `sh:sparql` rules, and the server never consults
  it when validating.
- **Options are IRIs, not strings** (`DESIGN.md §1`). A token like `"veganMiso"` on the wire
  lifts to `food:veganMiso` via `"@type": "@vocab"`. Because an option is a node rather than a
  string, a SPARQL rule can ask questions *about* it — the ramen rule reads
  `?value food:excludedByDiet "vegan"` and so names no topping at all.
- **The SHACL → JSON Forms translation** (`DESIGN.md §2`, `shacl/jsonforms.py`), row by row.
  Notably `oneOf` with `const`/`title` over a bare `enum`, because it is the only draft-07
  construct JSON Forms renders with human labels; and layout from `sh:group`, so form structure
  is modelled data rather than a convention invented here.
- **Reading `sh:name` as a field identifier** (`DESIGN.md §7`) — a deliberate deviation from the
  spec and the weakest point in the model. A form needs one stable token that is at once the JSON
  key, the context term and the error pointer. I can argue the two alternatives I rejected.
- **Errors carry JSON pointers** (`shacl/report.py`). `/toppings/1`, not a field name or a
  sentence, so the client mapping into JSON Forms is the identity function.
- **Closed shapes, and the boundary `sh:closed` cannot police** (`jsonld/lift.py`). Closure
  polices predicates; a JSON-LD keyword never becomes one. See below.
- **A language costs one file** (`DESIGN.md §3`), which is why the dish shapes name their
  property shapes rather than writing them inline — a blank node has no IRI for a translation to
  attach to.
- **The extensibility property.** The filesystem is the registry, and the contract suite
  parametrises over whatever is on disk, so commit `7cf2f2f` adds a third dish as two data files
  and inherits the whole suite.
- **The `SearchPort` boundary** and the degradation it buys: tests need no container, and an
  outage costs one endpoint rather than the service.

---

## AI-generated, not claimed as evidence of my own technical ability

- **All application source**, and the specific dish corpus content — the menu, prices and
  surcharges, as opposed to the modelling patterns above.
- **The test implementations.** 472 backend and 85 frontend tests. I own what they assert and
  why; I did not write them.
- **The custom JSON Forms renderers** in `frontend/src/renderers/`. I own the rule they follow
  (testers match on schema shape, never on a field name); not the JSON Forms API or the React.
- **Configuration and infrastructure.** `pyproject.toml`, `tsconfig.json`, both `Dockerfile`s,
  `compose.yaml`, `nginx.conf`, `.github/workflows/ci.yaml`, and the `scripts/` twins.
- **CSS.** `frontend/src/styles.css` is presentation only. Palette and typography follow
  datascience.ch's own stylesheet.
- **Prose.** This file, `README.md`, `DESIGN.md` and `CHECKLIST.md`. The technical claims in them
  are ones I checked against running code; the writing is not mine.

---

## What the review found

The finished repository was handed to a separate Claude Code session with no memory of having
written it, and asked to review it. **It found a critical defect in its own earlier work.** A
submission carrying its own `@context` replaced the generated one, lifted to an empty RDF graph,
matched no `sh:targetClass`, and was reported as conforming — a `201` with a priced receipt for
an order against which not one constraint had been applied:

```
POST /api/orders/ramen  {"data": {"@context": {}, "quantity": 99}}
  → 201  {"accepted": true, "total": 1584.00}
```

Also found: filter-expression injection through the search parameters, a CI step that could never
fail because a pipe swallowed pytest's exit code, a `sh:pattern` accepting a trailing newline its
own comment said it rejected, shell scripts committed without an executable bit (so the README's
first command failed on Linux), and some dead code. All are fixed, with regression tests, and
written up in `DESIGN.md §1`, `§6` and `§7`.

This is worth disclosing rather than quietly shipping: the code was tested, linted, type-checked
and CI-green, and wrong in the one way a validation service must not be wrong. Nothing in the
original test suite could have caught it, because every fixture was a well-formed submission.
The caveat is that the review was also AI-performed — it found this defect; I cannot claim it
found every defect.

---

## Known gaps

The German, French and Italian translations in `backend/src/food_api/data/i18n/` are AI-produced
and unreviewed by a native speaker. **The Romansh (`rm.ttl`) has been reviewed by nobody and
should be treated as a placeholder** — it is included because the architecture makes a language
cost one file, and omitting Switzerland's fourth national language would have been a decision
rather than a constraint. The file says so in its own header.

---

No AI-generated code was committed without being executed. Every claim in `README.md` about what
the system does is re-checked by the CI smoke-test job on every push, so a claim that stops being
true fails the build rather than persisting in a document. At the time of writing: 472 backend
and 85 frontend tests pass, backend coverage is 93%, and `ruff`, `ty` and `eslint` are clean.
