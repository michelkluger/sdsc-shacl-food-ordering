# SHACL-Driven Food Ordering API

A food-ordering service whose **entire form logic lives in JSON-LD documents and SHACL shapes**.
The backend generates the form a client renders, and validates what comes back, from the same
shape, in five languages.

Adding a dish is adding two data files. Adding a language is adding one. Neither needs a line of
code, a route, or a frontend change.

> SDSC Software R&D Engineer task 5. See [`DESIGN.md`](DESIGN.md) for the modelling decisions and
> [`AI_USAGE.md`](AI_USAGE.md) for the mandatory AI usage disclaimer.

```
                          ┌─→ JSON Schema      ─┐
sh:PropertyShape ─────────┼─→ JSON Forms UI    ─┼─→ the browser renders it
   + vocabulary           └─→ JSON-LD @context ─┘
                                    │
submitted JSON ──── lifted with that context ──→ pySHACL ──→ violations, by JSON pointer
```

Three artefacts, one source, generated in one pass — so the form, the validator and the error
messages cannot drift apart.

---

## Quick start

**Everything in Docker** — needs only Docker:

```bash
git clone <this-repo> && cd sdsc
cp .env.example .env
docker compose up --build
```

- Frontend → <http://localhost:5173>
- API docs → <http://localhost:8000/api/docs>
- Meilisearch → <http://localhost:7700>

**Local development** — needs [uv](https://docs.astral.sh/uv/) and [bun](https://bun.sh),
Meilisearch stays in Docker:

```bash
./scripts/setup.sh      # prerequisites → deps → Meilisearch → validate corpus → seed
bun install --cwd frontend
./scripts/dev.sh        # API and Vite on the host, both with reload
```

On Windows PowerShell: `./scripts/setup.ps1`, `./scripts/dev.ps1`, `./scripts/check.ps1`.

> Port 7700 already in use? Set `MEILI_PORT` in `.env` — every port is configurable there.

**Verify it works:**

```bash
./scripts/check.sh          # ruff, ty, backend tests, frontend tests, coverage gate
./scripts/check.sh --all    # also the integration tests against a live Meilisearch
```

---

## Try it

```bash
# The menu, discovered from the filesystem
curl localhost:8000/api/dishes

# A form, generated from ramen's SHACL shape at startup
curl localhost:8000/api/dishes/ramen/form | jq '.schema.properties | keys'
#  ["broth","customerName","customerNote","extraNoodles","noodleFirmness",
#   "pickupTime","quantity","spiceLevel","toppings"]

# A valid order. The fixture files are literally valid request bodies.
curl -X POST localhost:8000/api/orders/ramen -H 'content-type: application/json' \
     -d @backend/tests/fixtures/orders/ramen/valid.json

# An order that breaks a cross-field rule no JSON Schema could express
curl -X POST localhost:8000/api/orders/ramen -H 'content-type: application/json' \
     -d '{"data":{"broth":"veganMiso","noodleFirmness":"firm","spiceLevel":9,
                  "toppings":["chashu"],"quantity":1,"customerName":"You"}}'
```

```jsonc
// 422, application/problem+json
{
  "type": "https://sdsc.example/problems/shacl-validation",
  "title": "The order does not satisfy the dish's constraints",
  "status": 422,
  "dish": "ramen",
  "violations": [
    { "pointer": "/spiceLevel",  "constraint": "MaxInclusiveConstraintComponent",
      "message": "Spice level runs from 0 to 5.", "value": 9 },
    { "pointer": "/toppings/0",  "constraint": "SPARQLConstraintComponent",
      "message": "Chashu pork is not available with a vegan broth.", "value": "chashu" }
  ]
}
```

The pointer addresses the **offending array element**, so the client attaches the message to the
exact chip the user picked. On the frontend the mapping is the identity function: Ajv addresses
errors by `instancePath`, which is also a JSON pointer.

```bash
# Search, including by an option a dish merely offers
curl 'localhost:8000/api/search?q=cashew'          # → poke-bowl
curl 'localhost:8000/api/search?allergenFree=fish&diet=vegan-available'
```

This is what the dish rail in the UI calls. Its filter chips are built from the facet counts the
response carries, so a dish contributing a new diet or allergen adds a filter with no frontend
change. Stop the Meilisearch container and the rail falls back to `/api/dishes`, hides the
filters and says why — forms and ordering keep working.

### In five languages

```bash
curl -H 'Accept-Language: rm' localhost:8000/api/dishes/poke-bowl/form   | jq '[.schema.properties[].title]'
#  ["Basa","Proteina","Salsa","Croccant","Quantitad","Tes num","Ura da retratga",…]

curl -X POST 'localhost:8000/api/orders/ramen?lang=de' -H 'content-type: application/json'      -d '{"data":{"broth":"veganMiso","noodleFirmness":"firm","spiceLevel":9,
                  "toppings":["chashu"],"quantity":1,"customerName":"Du"}}' | jq '.violations[].message'
#  "Die Schärfe reicht von 0 bis 5."
#  "Dieses Topping gibt es nicht zur veganen Brühe."
```

German, French, Italian, **Romansh** and English. Only what people *read* changes: the JSON
keys, the option values, the constraints and the price are identical in every language, so a
form rendered in Romansh is validated and priced by the English one.

---

## Adding a language

One file, `backend/src/food_api/data/i18n/<lang>.ttl`. It declares nothing — it attaches
language-tagged literals to terms and shapes that already exist:

```turtle
food:RamenBrothProperty
    rdfs:label "Brühe"@de ;
    sh:message "Wähle genau eine Brühe."@de .
```

Only what genuinely differs needs translating. "Nori" is called Nori in all five, so it keeps
one untagged label and the fallback chain resolves it.

---

## Adding a dish

Two files. No code.

```
backend/src/food_api/data/dishes/<slug>/dish.jsonld   # catalogue entry
backend/src/food_api/data/dishes/<slug>/shape.ttl     # SHACL order shape
```

```bash
uv run --project backend food-api check    # parses every dish and reports what it derived
docker compose restart api && docker compose run --rm seed
```

The third dish, Poke Bowl, was added exactly this way. `git show --stat 7cf2f2f` is two data
files and nothing else — and that dish inherited 13 contract tests without a line of test code
being written for it.

---

## API

| Method | Path | |
|---|---|---|
| `GET` | `/api/healthz` | Per-component health. `degraded` means search is down, ordering is not |
| `GET` | `/api/dishes` | The menu, as `{data, count}` |
| `GET` | `/api/dishes/{slug}` | One catalogue entry |
| `GET` | `/api/dishes/{slug}/form` | JSON Forms `schema` + `uischema` + the JSON-LD `@context` |
| `POST` | `/api/orders/{slug}` | Validate against the dish's shape; `201` or `422` with violations |
| `GET` | `/api/search` | `q`, `cuisine`, `diet`, `allergenFree`, `limit` → hits + facets |
| `GET` | `/api/docs` | OpenAPI |

Every error — unknown dish, malformed body, constraint violation, search outage — uses one
[RFC 9457](https://www.rfc-editor.org/rfc/rfc9457) problem-details envelope.

Every endpoint that returns readable text negotiates language via `?lang=` or `Accept-Language`,
and echoes the result in `Content-Language`.

---

## Layout

Laid out to match the [official FastAPI full-stack
template](https://github.com/fastapi/full-stack-fastapi-template) — `api/routes/`, `api/deps.py`,
`api/main.py`, `core/config.py`, `models.py` — so anyone who knows that template can navigate
this one.

```
backend/src/food_api/
  main.py        app factory + lifespan
  models.py      Pydantic request/response models (DishPublic, OrderCreate, …)
  api/
    main.py      the aggregated api_router
    deps.py      catalog, search and language dependencies
    routes/      dishes · orders · search · health
  core/          config · errors (RFC 9457) · language negotiation
  data/          vocab/ · shapes/ · context/ · i18n/{de,fr,it,rm}.ttl
                 dishes/{french-tacos,ramen,poke-bowl}/
  catalog/       filesystem discovery; the registry IS the directory listing
  shacl/         introspect → jsonforms → validate → report
  jsonld/        lift a payload into RDF with the generated context
  search/        SearchPort protocol · Meilisearch impl · in-memory fake
backend/tests/   unit · contract (parametrised over every dish) · api · integration
frontend/src/    React + @jsonforms/react; no dish-specific branch anywhere
  renderers/     chips · option cards · stepper/slider · date-time with a "Now" button —
                 every one matched on schema shape, never on a field name
  DishBrowser    search box + facet filters, built from the facets the server returns
  OrderSummary   sticky running total, priced from the server's `pricing` block
  theme.ts       light / dark / follow-system, remembered per browser
scripts/         setup · dev · check, in Bash and PowerShell
```

The setup scripts are thin on purpose: they check prerequisites and delegate to the tested
`food-api` CLI, so the Bash and PowerShell versions cannot drift apart.

---

## Quality gates

| | |
|---|---|
| Lint | `ruff` — ~20 rule families incl. bugbear, bandit, pylint, pathlib |
| Types | `ty` (Astral) on `src` and `tests` |
| Backend tests | 378, coverage gate at 85% |
| Frontend | eslint + `tsc --noEmit` + 86 vitest tests |
| CI | 4 jobs: lint · tests (Meilisearch **service container**, so integration tests really run) · frontend · a Docker stack smoke test that re-checks this README's claims |

---

## What I prioritised, and what I left out

**Prioritised**, because they are what the task is actually about:

- the derivation of schema + UI schema + JSON-LD context from one shape, and the reverse
  mapping that gives every violation a JSON pointer;
- making a language cost one file, in a country with four of them;
- constraints worth validating — cardinality, enumerations, ranges, closure, and one
  `sh:sparql` cross-field rule per dish that no JSON Schema can express;
- making "add a dish without touching code" a tested property rather than a claim;
- reproducibility: one command from a clean clone, and CI that would catch it regressing.

**Left out deliberately:** persistence, auth, and Meilisearch relevance tuning. The brief asks
for none of them and each would have cost time better spent on the modelling.

**Known limitations** are listed honestly in [`DESIGN.md` §7](DESIGN.md) — including the
`sh:name` deviation from the SHACL spec, the fact that cross-field rules cannot reach the client
before submission, and that the Romansh translation is unreviewed. [§8](DESIGN.md) lists what I
would do next, in order.

The visual language is borrowed from [datascience.ch](https://datascience.ch): their indigo
(`#5561a6`), deep navy (`#26235c`), pale lilac ground and Space Grotesk headings, read from
their stylesheet rather than eyeballed.

---

## Licence

MIT — see [`LICENSE`](LICENSE).
