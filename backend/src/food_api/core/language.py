"""Language negotiation.

The four Swiss national languages plus English. A client picks one with ``?lang=``, or lets
``Accept-Language`` decide, or gets English.

The rules live here, free of FastAPI, so they can be tested as plain functions; the dependency
that applies them to a request is in ``api/deps.py`` with every other dependency. Keeping the
decision in one place is what lets the resolved language be echoed in ``Content-Language`` on
every response that carries translated text.
"""

from __future__ import annotations

from food_api.shacl.introspect import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES


def parse_accept_language(header: str | None) -> list[tuple[str, float]]:
    """Parse an ``Accept-Language`` header into (tag, quality) pairs, best first.

    Malformed entries are skipped rather than raising: a bad header from one browser should
    degrade to the default language, not fail the request.
    """
    if not header:
        return []

    parsed: list[tuple[str, float]] = []
    for index, part in enumerate(header.split(",")):
        token, _, params = part.strip().partition(";")
        tag = token.strip().lower()
        if not tag:
            continue

        quality = 1.0
        if params.strip().startswith("q="):
            try:
                quality = float(params.strip()[2:])
            except ValueError:
                quality = 1.0
        # The index keeps the original order stable among equal qualities, which is what
        # browsers actually mean by the order they send.
        parsed.append((tag, quality - index * 1e-6))

    parsed.sort(key=lambda item: item[1], reverse=True)
    return parsed


def negotiate(header: str | None, override: str | None = None) -> str:
    """Choose a supported language.

    An explicit ``?lang=`` wins over the header, because it is a deliberate act by the user -
    typically clicking the language switcher - and should not be overridden by their browser's
    configuration. Unsupported values fall through rather than erroring: asking for Spanish is
    not a client mistake worth a 400, it is just something this menu does not have.
    """
    if override:
        candidate = override.strip().lower()
        base = candidate.partition("-")[0]
        if base in SUPPORTED_LANGUAGES:
            return base

    for tag, _ in parse_accept_language(header):
        if tag == "*":
            break
        base = tag.partition("-")[0]
        if base in SUPPORTED_LANGUAGES:
            return base

    return DEFAULT_LANGUAGE
