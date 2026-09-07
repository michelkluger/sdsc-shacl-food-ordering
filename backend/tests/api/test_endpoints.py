"""HTTP-level tests.

These run the real app in-process over ASGI, with search stubbed. They cover the wire contract -
status codes, the problem-details envelope, aliasing - rather than re-testing validation logic
that ``tests/contract`` already covers per dish.
"""

from __future__ import annotations

from httpx import AsyncClient

from food_api.core.errors import PROBLEM_CONTENT_TYPE
from food_api.search.client import InMemorySearch
from tests.conftest import load_fixture

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_UNPROCESSABLE = 422
HTTP_UNAVAILABLE = 503


async def test_healthz_reports_components(client: AsyncClient) -> None:
    response = await client.get("/api/healthz")
    body = response.json()

    assert response.status_code == HTTP_OK
    assert body["status"] == "ok"
    assert {component["name"] for component in body["components"]} == {"catalog", "search"}
    assert "ramen" in body["dishes"]


async def test_healthz_is_degraded_not_down_when_search_is_unreachable(
    client: AsyncClient,
    search: InMemorySearch,
) -> None:
    search.available = False
    body = (await client.get("/api/healthz")).json()

    assert body["status"] == "degraded"
    search_component = next(c for c in body["components"] if c["name"] == "search")
    assert search_component["status"] == "unavailable"


async def test_list_dishes_is_a_wrapped_collection(client: AsyncClient) -> None:
    """Collections are `{data, count}`, the shape the FastAPI template uses everywhere."""
    body = (await client.get("/api/dishes")).json()

    assert {dish["slug"] for dish in body["data"]} >= {"ramen", "french-tacos"}
    assert body["count"] == len(body["data"])
    assert "basePrice" in body["data"][0]


async def test_get_form_returns_the_three_generated_artefacts(client: AsyncClient) -> None:
    response = await client.get("/api/dishes/ramen/form")
    body = response.json()

    assert response.status_code == HTTP_OK
    assert body["schema"]["type"] == "object"
    assert body["uischema"]["type"] == "VerticalLayout"
    assert body["@context"]["broth"]["@type"] == "@vocab"
    assert body["shapeIri"].endswith("RamenOrderShape")


async def test_unknown_dish_returns_a_problem_listing_what_exists(client: AsyncClient) -> None:
    response = await client.get("/api/dishes/pizza/form")
    body = response.json()

    assert response.status_code == HTTP_NOT_FOUND
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert body["type"].endswith("unknown-dish")
    assert "ramen" in body["availableDishes"]


async def test_valid_order_is_accepted_with_a_priced_receipt(client: AsyncClient) -> None:
    payload = load_fixture("ramen", "valid.json")["data"]
    response = await client.post("/api/orders/ramen", json={"data": payload})
    body = response.json()

    assert response.status_code == HTTP_CREATED
    assert body["accepted"] is True
    assert body["orderId"].startswith("urn:food:order:")
    assert body["total"] > 0
    assert body["currency"] == "CHF"
    # The receipt echoes what was submitted, so a client can reconcile without re-sending.
    assert body["data"] == payload


async def test_invalid_order_returns_pointered_violations(client: AsyncClient) -> None:
    fixture = load_fixture("ramen", "invalid_vegan_topping.json")
    response = await client.post("/api/orders/ramen", json={"data": fixture["data"]})
    body = response.json()

    assert response.status_code == HTTP_UNPROCESSABLE
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert body["type"].endswith("shacl-validation")
    assert body["dish"] == "ramen"

    pointers = {violation["pointer"] for violation in body["violations"]}
    assert "/toppings/1" in pointers
    assert all(violation["message"] for violation in body["violations"])


async def test_order_for_unknown_dish_is_404_not_422(client: AsyncClient) -> None:
    """The dish is resolved before validation, so a typo in the URL is not a form error."""
    response = await client.post("/api/orders/pizza", json={"data": {}})
    assert response.status_code == HTTP_NOT_FOUND


async def test_malformed_body_uses_the_same_problem_envelope(client: AsyncClient) -> None:
    response = await client.post("/api/orders/ramen", json={"data": "not-an-object"})
    body = response.json()

    assert response.status_code == HTTP_BAD_REQUEST
    assert body["type"].endswith("malformed-request")
    assert body["status"] == HTTP_BAD_REQUEST


async def test_empty_submission_reports_every_missing_required_field(client: AsyncClient) -> None:
    response = await client.post("/api/orders/ramen", json={"data": {}})
    body = response.json()

    assert response.status_code == HTTP_UNPROCESSABLE
    fields = {violation["field"] for violation in body["violations"]}
    assert {"broth", "noodleFirmness", "spiceLevel", "quantity", "customerName"} <= fields


async def test_a_dish_cannot_be_ordered_against_another_dishs_shape(client: AsyncClient) -> None:
    """A ramen payload posted to the tacos endpoint must be rejected, not silently accepted."""
    payload = load_fixture("ramen", "valid.json")["data"]
    response = await client.post("/api/orders/french-tacos", json={"data": payload})
    assert response.status_code == HTTP_UNPROCESSABLE


async def test_a_json_ld_keyword_cannot_buy_an_unvalidated_receipt(client: AsyncClient) -> None:
    """The bypass, asserted at the layer that actually shipped it.

    `tests/contract/test_payload_boundary.py` covers the rule for every dish. This one is here
    because the bug was only ever visible from outside: `POST` a payload carrying its own
    `@context` and the API answered `201` with a priced receipt for an order no constraint had
    been applied to. A unit test asserting `not conforms` would not have shown that.
    """
    response = await client.post(
        "/api/orders/ramen",
        json={"data": {"@context": {}, "quantity": 99}},
    )
    body = response.json()

    assert response.status_code == HTTP_UNPROCESSABLE
    assert response.headers["content-type"].startswith(PROBLEM_CONTENT_TYPE)
    assert [violation["constraint"] for violation in body["violations"]] == ["MalformedPayload"]
    assert "@context" in body["violations"][0]["message"]


async def test_a_keyword_refusal_is_translated_like_any_other_problem(
    client: AsyncClient,
) -> None:
    """It is still a 422 in the problem envelope, so a client handles it with everything else."""
    response = await client.post(
        "/api/orders/ramen?lang=de",
        json={"data": {"@type": "food:NotAnOrder"}},
    )
    assert response.status_code == HTTP_UNPROCESSABLE
    assert response.headers["content-language"] == "de"


async def test_search_returns_hits_and_facets(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get("/api/search", params={"q": "ramen"})).json()

    assert body["query"] == "ramen"
    assert [hit["slug"] for hit in body["hits"]] == ["ramen"]
    assert body["facets"]["cuisine"] == {"Japanese": 1}


async def test_search_finds_a_dish_by_an_option_label(seeded_client: AsyncClient) -> None:
    """Option labels are indexed, so a dish is findable by something it merely offers."""
    body = (await seeded_client.get("/api/search", params={"q": "chashu"})).json()
    assert [hit["slug"] for hit in body["hits"]] == ["ramen"]


async def test_search_filters_by_cuisine(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get("/api/search", params={"cuisine": "French"})).json()
    assert [hit["slug"] for hit in body["hits"]] == ["french-tacos"]


async def test_a_filter_value_cannot_inject_a_clause(seeded_client: AsyncClient) -> None:
    """Meilisearch filters are an expression language, and `cuisine` is interpolated into one.

    Unescaped, `Japanese' OR cuisine = 'French` would have closed the literal and appended a
    clause of the client's choosing. Quoted correctly it is one absurd cuisine name that matches
    nothing - which is the right answer, and is what this asserts.
    """
    body = (
        await seeded_client.get(
            "/api/search",
            params={"cuisine": "Japanese' OR cuisine = 'French"},
        )
    ).json()

    assert body["hits"] == []


async def test_search_excludes_dishes_by_allergen(seeded_client: AsyncClient) -> None:
    body = (await seeded_client.get("/api/search", params={"allergenFree": "gluten"})).json()
    assert all("gluten" not in hit["allergens"] for hit in body["hits"])


async def test_search_degrades_without_taking_the_api_down(
    client: AsyncClient,
    search: InMemorySearch,
) -> None:
    """The point of the port: search failing must not stop anyone ordering."""
    search.available = False

    response = await client.get("/api/search", params={"q": "ramen"})
    body = response.json()
    assert response.status_code == HTTP_UNAVAILABLE
    assert body["type"].endswith("search-unavailable")

    payload = load_fixture("ramen", "valid.json")["data"]
    assert (await client.post("/api/orders/ramen", json={"data": payload})).status_code == (
        HTTP_CREATED
    )
    assert (await client.get("/api/dishes/ramen/form")).status_code == HTTP_OK


async def test_search_limit_is_bounded(client: AsyncClient) -> None:
    assert (await client.get("/api/search", params={"limit": 999})).status_code == HTTP_BAD_REQUEST


async def test_openapi_document_is_served(client: AsyncClient) -> None:
    response = await client.get("/api/openapi.json")
    assert response.status_code == HTTP_OK
    assert "/api/orders/{slug}" in response.json()["paths"]


# ---------------------------------------------------------------------------
# Language negotiation over HTTP
# ---------------------------------------------------------------------------


async def test_form_defaults_to_english(client: AsyncClient) -> None:
    response = await client.get("/api/dishes/ramen/form")
    assert response.json()["language"] == "en"
    assert response.headers["content-language"] == "en"


async def test_form_honours_accept_language(client: AsyncClient) -> None:
    response = await client.get(
        "/api/dishes/ramen/form", headers={"Accept-Language": "de-CH,de;q=0.9,en;q=0.5"}
    )
    body = response.json()

    assert body["language"] == "de"
    assert body["schema"]["properties"]["broth"]["title"] == "Brühe"
    assert response.headers["content-language"] == "de"


async def test_lang_query_parameter_beats_the_header(client: AsyncClient) -> None:
    """The switcher must win over the browser's configuration."""
    response = await client.get(
        "/api/dishes/ramen/form", params={"lang": "rm"}, headers={"Accept-Language": "de"}
    )
    assert response.json()["language"] == "rm"


async def test_unsupported_language_degrades_to_english_rather_than_erroring(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/dishes/ramen/form", params={"lang": "es"})
    assert response.status_code == HTTP_OK
    assert response.json()["language"] == "en"


async def test_form_advertises_every_available_language(client: AsyncClient) -> None:
    """So a client can build a switcher without a hardcoded list that could fall out of step."""
    body = (await client.get("/api/dishes/ramen/form")).json()
    assert set(body["availableLanguages"]) == {"en", "de", "fr", "it", "rm"}


async def test_dish_list_is_translated(client: AsyncClient) -> None:
    body = (await client.get("/api/dishes", params={"lang": "it"})).json()
    ramen = next(dish for dish in body["data"] if dish["slug"] == "ramen")
    assert ramen["cuisine"] == "Giapponese"


async def test_violation_messages_are_translated(client: AsyncClient) -> None:
    fixture = load_fixture("ramen", "invalid_spice_out_of_range.json")
    response = await client.post(
        "/api/orders/ramen", params={"lang": "fr"}, json={"data": fixture["data"]}
    )
    messages = [violation["message"] for violation in response.json()["violations"]]

    assert response.status_code == HTTP_UNPROCESSABLE
    assert any("piquant" in message for message in messages), messages


async def test_cross_field_rule_message_is_translated(client: AsyncClient) -> None:
    """The `sh:sparql` path, which needs its message resolved from the shapes graph."""
    fixture = load_fixture("ramen", "invalid_vegan_topping.json")
    response = await client.post(
        "/api/orders/ramen", params={"lang": "de"}, json={"data": fixture["data"]}
    )
    violation = next(v for v in response.json()["violations"] if v["pointer"] == "/toppings/1")

    assert violation["message"] == "Dieses Topping gibt es nicht zur veganen Brühe."


async def test_a_form_fetched_in_one_language_submits_in_another(client: AsyncClient) -> None:
    """The wire contract does not move with the reader.

    A user reading Romansh sends exactly the tokens an English reader sends, so a client may
    switch language between rendering the form and submitting it without re-mapping anything.
    """
    form = (await client.get("/api/dishes/ramen/form", params={"lang": "rm"})).json()
    assert set(form["schema"]["properties"]) == {
        "broth",
        "customerName",
        "customerNote",
        "extraNoodles",
        "noodleFirmness",
        "pickupTime",
        "quantity",
        "spiceLevel",
        "toppings",
    }

    payload = load_fixture("ramen", "valid.json")["data"]
    response = await client.post("/api/orders/ramen", params={"lang": "it"}, json={"data": payload})
    assert response.status_code == HTTP_CREATED


async def test_receipt_carries_the_translated_dish_name(client: AsyncClient) -> None:
    payload = load_fixture("french-tacos", "valid.json")["data"]
    body = (
        await client.post("/api/orders/french-tacos", params={"lang": "fr"}, json={"data": payload})
    ).json()
    assert body["dishName"] == "Tacos français"
