# AI usage disclaimer

The task instructions make this disclaimer mandatory and ask it to separate **human-owned** work
from **AI-generated, non-owned** work. This document is written to be accurate rather than
flattering, because an inflated ownership claim is worse than an honest one.

> **⚠️ Before submitting, edit this file.** It currently records how the repository was
> produced. Only you can say which parts you have reviewed deeply enough to defend in a
> technical conversation. Move items between the two sections to match the truth after your
> own review, and delete this box.

---

## How this repository was produced

This project was built in a single working session with **Claude Opus 5, driven through Claude
Code**, from the Task 5 brief in `Tasks_RSDE_2026.pdf`.

The working method was:

1. The task was read from the PDF and a plan was agreed before any code was written, including
   explicit decisions on the frontend stack, the setup-script style, and the repository target.
2. The SHACL and JSON-LD modelling was **probed against pySHACL before being committed** rather
   than assumed — several of the design notes in `DESIGN.md §6` are findings from that probing,
   not from documentation.
3. Every layer was run and verified as it was written: the validation core against a scratch
   harness, the API over ASGI, the integration tests against a live Meilisearch container, and
   the whole stack through Docker Compose.
4. Lint (`ruff`), type checking (`ty`), 378 backend tests and 86 frontend tests all pass.

**Practically all source code in this repository was AI-generated.** The human contribution was
direction, scope decisions, and review.

---

## Human-owned

> Fill this in yourself. List what you have read, understood, and can explain, modify and defend
> under questioning. Suggested candidates, in the order they are most worth owning:
>
> - the **modelling decisions** in `DESIGN.md` §1 — the vocabulary/shape split, IRI-valued
>   options via `@type: @vocab`, closed shapes, and which cross-field rules exist and why;
> - the **translation table** in `DESIGN.md` §2 and its implementation in
>   `backend/src/food_api/shacl/jsonforms.py`;
> - the **error-pointer mapping** in `backend/src/food_api/shacl/report.py`, and why the
>   backend emits JSON pointers at all;
> - the **`SearchPort` boundary** and the degradation behaviour it buys;
> - the **translation model** in `DESIGN.md` §3 — why a language costs one file, why the
>   property shapes had to be named for that to work, and the invariant that translation
>   changes only what people read;
> - the **`sh:name` deviation** documented in `DESIGN.md` §7, which is the single most
>   questionable modelling choice here and the one most likely to be probed.
>
> Anything you have not actually read line by line belongs in the section below. That is not a
> weakness — it is the disclosure the brief is asking for.

---

## AI-generated, not claimed as evidence of my own technical ability

> Move items out of here as you review them.

- **The full test suites.** `backend/tests/` (unit, contract, API, integration) and
  `frontend/src/*.test.tsx`. They pass and they test real behaviour — the contract suite in
  particular is the mechanism behind the "add a dish without touching code" claim — but they
  were AI-authored.
- **Boilerplate and configuration.** `pyproject.toml`, `tsconfig.json`, `eslint.config.js`,
  `vite.config.ts`, `.pre-commit-config.yaml`, both `Dockerfile`s, `nginx.conf`, `compose.yaml`.
- **The CI workflow**, `.github/workflows/ci.yaml`.
- **The setup, dev and check scripts** in `scripts/`, in both Bash and PowerShell.
- **CSS.** `frontend/src/styles.css` is presentation only and carries no logic. Its palette and
  typography are taken from datascience.ch's own stylesheet.
- **Translations.** The German, French and Italian content in `backend/src/food_api/data/i18n/`
  is AI-produced. It reads correctly to me, but it has not been reviewed by a native speaker.

  **The Romansh (`rm.ttl`) has not been reviewed by anyone and should be treated as a
  placeholder.** It is included because the architecture makes a language cost one file and
  omitting Switzerland's fourth national language would have been a decision rather than a
  constraint — but shipping an unreviewed translation as finished work would be a different
  kind of mistake, and the file says so in its own header.
- **Prose.** This file, `README.md`, `DESIGN.md` and `CHECKLIST.md` were drafted by AI from the
  work actually done. The technical claims in them were verified against running code; the
  writing is not mine.

---

## What was not used

No AI-generated code was committed without being executed. Every claim in `README.md` about
what the system does was checked against a running instance, and the CI smoke-test job re-checks
the load-bearing ones on every push, so a claim that stops being true fails the build rather
than quietly persisting in a document.
