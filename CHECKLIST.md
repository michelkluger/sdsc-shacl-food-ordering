# Criteria checklist

Every requirement from `Tasks_RSDE_2026.pdf` — the general instructions on p.2 and the Task 5
brief on pp.9–10 — mapped to where it is satisfied. The point is that each row names a file, a
command or a commit rather than an assurance.

---

## Task 5 requirements (pp. 9–10)

| # | Requirement | Status | Evidence |
|---|---|---|---|
| 1 | Small but complete food-ordering application | ✅ | Backend + frontend + search, `docker compose up --build` |
| 2 | Backend drives form logic from JSON-LD and SHACL | ✅ | `backend/src/food_api/data/`; nothing about a form is written in Python |
| 3 | Frontend optional, minimal, only displays what the backend provides | ✅ | `frontend/src/` — no dish name appears in any code path; the only mentions are one explanatory comment and the invented dish in the tests |
| 4 | Backend in a language of my choice | ✅ | Python 3.13 + FastAPI |
| 5 | Configure and order **French Tacos** | ✅ | `data/dishes/french-tacos/` |
| 6 | Configure and order **Ramen** | ✅ | `data/dishes/ramen/` |
| 7 | Backend stores the JSON-LD documents and SHACL shapes per dish | ✅ | `dish.jsonld` + `shape.ttl` per directory |
| 8 | Shapes define **required fields** | ✅ | `sh:minCount` → JSON Schema `required` |
| 9 | Shapes define **allowed values** | ✅ | `sh:in` → `oneOf` with labels from the vocabulary |
| 10 | Shapes define **cardinality** | ✅ | `sh:minCount`/`sh:maxCount` → `minItems`/`maxItems` (1..2 meats, 0..5 toppings) |
| 11 | Shapes define **simple validation rules** | ✅ | ranges, lengths, patterns, datatypes, `sh:closed`, plus one `sh:sparql` rule per dish |
| 12 | Form definition exposed machine-readably (e.g. JSON Forms schema + UI schema) | ✅ | `GET /api/dishes/{slug}/form` returns `schema`, `uischema` and the JSON-LD `@context` |
| 13 | SHACL/JSON-LD → form schema translation happens **exclusively on the backend** | ✅ | `shacl/jsonforms.py`. The frontend imports no RDF library; `frontend/package.json` has no such dependency |
| 14 | Endpoint to retrieve the form schema for a dish | ✅ | `GET /api/dishes/{slug}/form` |
| 15 | Endpoint to submit and validate a filled-in form | ✅ | `POST /api/orders/{slug}` |
| 16 | Validation happens on the backend | ✅ | `shacl/validate.py` — pySHACL is the authority; the generated JSON Schema is never consulted server-side |
| 17 | Payload validated against the SHACL shapes | ✅ | `pyshacl.validate(..., advanced=True)` against that dish's shapes graph |
| 18 | **Structured** errors returned when constraints are violated | ✅ | RFC 9457 problem details + a `violations[]` array addressed by JSON pointer |
| 19 | Frontend: select a dish | ✅ | `frontend/src/App.tsx` — the list is fetched, never declared |
| 20 | Frontend: render the schema returned by the backend | ✅ | `frontend/src/DishForm.tsx` via `@jsonforms/react` |
| 21 | Frontend: submit and show confirmation or validation errors | ✅ | Receipt on 201; violations mapped onto controls on 422 |
| 22 | Frontend contains no dish-specific form logic or definitions | ✅ | Tests render **"Blorp Stew"**, a dish invented in the test file that the backend has never heard of |
| 23 | No persistence required | ✅ | None. Receipts are computed, not stored |
| 24 | *If time allows:* a third dish, added purely as a JSON-LD document and SHACL shape, zero frontend changes | ✅ | **Poke Bowl.** `git show --stat 7cf2f2f` → two data files, nothing else |
| 25 | Written section: modelling choices, translation, limitations, assumptions | ✅ | [`DESIGN.md`](DESIGN.md) §1, §2, §6 |
| 26 | Presented in a repository | ✅ | Git history in meaningful, reviewable commits |
| 27 | Reproducible | ✅ | `docker compose up --build`, or `./scripts/setup.sh` |
| 28 | Well-documented | ✅ | README, DESIGN, AI_USAGE, this file, and comments that explain *why* |
| 29 | Clear README with setup instructions | ✅ | [`README.md`](README.md) |

---

## Beyond the brief

Neither was asked for. Both were added because they exercise the same architecture rather than
sitting beside it, and each is a claim the tests hold to.

| Addition | Why it belongs | Evidence |
|---|---|---|
| **Meilisearch**, in Docker | Search documents are projected from the loaded catalogue including option labels, so a new dish is searchable with no indexing rule written for it | `search/indexer.py`; `GET /api/search?q=cashew` → poke-bowl |
| **Five languages** — DE, FR, IT, RM, EN | A language costs one `i18n/<lang>.ttl` file that declares nothing and changes no code, mirroring "a dish costs two files" | `tests/contract/test_every_language.py`, 15 dish×language combinations checked in CI |
| **Custom JSON Forms renderers** | The vanilla array control needed an "add row" click per value; these match on schema *shape* — array-of-enum, short enum, bounded integer, date-time — never on a field name | `frontend/src/renderers/`, tested against an invented dish |
| **A sticky order summary** | The total was only visible at the bottom of the form; it is now beside it, with a line per priced choice, labelled from the schema the server sent | `frontend/src/OrderSummary.tsx`, `pricing.ts` |
| **Light / dark / system** | Three states, not two, so "follow my system" survives touching the toggle | `frontend/src/theme.ts` |
| **SDSC visual language** | Indigo `#5561a6`, navy `#26235c`, Space Grotesk headings and Switzer body — read from datascience.ch's own stylesheet, not eyeballed. Every colour is a token; SVG icons rather than Unicode glyphs, which render as colour emoji | `frontend/src/styles.css`, `Icon.tsx` |

---

## "What we will be looking at" (p. 10)

| Criterion | Evidence |
|---|---|
| **Backend architecture** — clean, well-structured SHACL/JSON-LD processing, easy to extend | One pipeline: `introspect → jsonforms → lift → validate → report`. `introspect.py` is the only module that touches an rdflib graph; everything downstream consumes dataclasses. Extension point is a directory, not a function |
| **Separation of concerns** — a new dish needs no frontend change or hardcoded frontend logic | Commit `7cf2f2f` is two data files. `git show --name-only 7cf2f2f \| grep -v '^backend/src/food_api/data/'` returns nothing |
| **Validation** — meaningful, with clear structured errors | Every constraint class exercised, incl. three `sh:sparql` cross-field rules. Errors carry a JSON pointer to the offending array *element*, the constraint component, the value, and the shape's own `sh:message` |
| **Approach to testing** — evidence valid and invalid submissions were tested | 378 backend + 72 frontend tests. 22 order fixtures across 3 dishes, each invalid one declaring the pointer and constraint it must trigger, exercised in all 5 languages. Integration tests run against real Meilisearch in CI |
| **Reproducibility** — clone and run without guesswork | One command. Prerequisites are checked with actionable messages; every version is pinned; CI builds the stack from scratch and smoke-tests it |

---

## General instructions (p. 2)

| Instruction | Where |
|---|---|
| What was implemented in the timeframe | [`README.md`](README.md) → *What I prioritised, and what I left out* |
| Assumptions and limitations | [`DESIGN.md` §6](DESIGN.md) — including the `sh:name` deviation from the SHACL spec |
| Extensions and improvements with more time | [`DESIGN.md` §7](DESIGN.md), ordered by value |
| **AI usage disclaimer (mandatory)** | [`AI_USAGE.md`](AI_USAGE.md) ⚠️ **edit before submitting** to record what you personally own |
| Quality over quantity | Three dishes, one pipeline, no dish-specific code path anywhere |
| Learning over producing | [`DESIGN.md` §5](DESIGN.md) records what pySHACL actually does, found by probing rather than by reading docs |
| Planning over executing | [`DESIGN.md` §1](DESIGN.md) states the decisions; commit messages state the reasoning |
| Prioritisation over completeness | Stated explicitly in the README rather than left to be inferred |
| Transparency over results | §5 records the mistakes and near-misses, including the one that would have made the validator accept everything |

---

## Engineering practice

| | |
|---|---|
| Formatting | `ruff format` — checked in CI |
| Linting | `ruff` with ~20 rule families (bugbear, bandit, pylint, pathlib, comprehensions…) |
| Type checking | `ty` on `src` and `tests`, clean with no blanket ignores |
| Tests | 378 backend (unit · contract · API · integration), 72 frontend |
| Coverage | Gate at 85% |
| CI | 4 jobs incl. a Docker stack smoke test that re-verifies the README's claims — every dish in every language — on every push |
| Pre-commit | `.pre-commit-config.yaml` — fast checks only |
| Dependencies | Every version pinned; `uv.lock` and `bun.lock` committed |
| Containers | Multi-stage builds, non-root user, healthchecks |
| Secrets | None committed. `.env` is gitignored, `.env.example` documents every variable |

---

## Before submitting

- [ ] **Edit [`AI_USAGE.md`](AI_USAGE.md)** — move items into *Human-owned* to match what you have
      actually reviewed and can defend. This is the one thing nobody else can do for you.
- [ ] **Have a Romansh speaker read `backend/src/food_api/data/i18n/rm.ttl`.** The mechanism is
      finished; that translation is machine-produced and unreviewed, and says so.
- [ ] Read [`DESIGN.md` §1, §3 and §6](DESIGN.md) closely — the `sh:name` deviation, the
      translation invariant, and the `ont_graph` finding are the likeliest interview questions.
- [ ] Push and confirm CI is green.
- [ ] Give the reviewers access (the repository is private by default).
- [ ] Tell them roughly how long it took, and when they can expect it.
