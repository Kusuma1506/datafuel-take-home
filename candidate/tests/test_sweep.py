from sweep import fetch_store_inventory, request_json


class FakePacer:
    def __init__(self):
        self.calls = 0

    def wait(self):
        self.calls += 1


class FakeResponse:
    def __init__(self, status_code, body=None, headers=None):
        self.status_code = status_code
        self._body = body or {}
        self.headers = headers or {}

    def json(self):
        return self._body


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, *args, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def item(sku_id, name, observed_at, price):
    return {
        "sku_id": sku_id,
        "name": name,
        "in_stock": True,
        "qty": 1,
        "price": price,
        "observed_at": observed_at,
    }


def test_request_json_paces_each_retry(monkeypatch):
    monkeypatch.setattr("sweep.time.sleep", lambda _: None)
    session = FakeSession([
        FakeResponse(503),
        FakeResponse(200, {"ok": True}),
    ])
    pacer = FakePacer()

    body, error = request_json(session, "http://portal.test", pacer=pacer)

    assert error is None
    assert body == {"ok": True}
    assert session.calls == 2
    assert pacer.calls == 2


def test_request_json_does_not_retry_permanent_4xx():
    session = FakeSession([FakeResponse(401)])
    pacer = FakePacer()

    body, error = request_json(session, "http://portal.test", pacer=pacer)

    assert body is None
    assert error == "http 401"
    assert session.calls == 1
    assert pacer.calls == 1


def test_inventory_pagination_dedupes_and_normalizes():
    first = item("SKU-1", "Old name", "2026-09-28T10:00:00+05:30", "237.50")
    repeated = item("SKU-1", "New name", "2026-09-28T05:01:00Z", 237.5)
    second = item("SKU-2", "Bread", "2026-09-28T05:02:00Z", 50)
    session = FakeSession([
        FakeResponse(200, {
            "items": [first], "partial": False, "next_cursor": "15",
            "meta": {"source": "origin"},
        }),
        FakeResponse(200, {
            "items": [repeated, second], "partial": False, "next_cursor": None,
            "meta": {"source": "origin"},
        }),
    ])

    status, reason, items = fetch_store_inventory(session, FakePacer(), "MUM-001", "2026-09-28T04:30:00Z")

    assert status == "complete"
    assert reason is None
    assert len(items) == 2
    by_sku = {row["sku_id"]: row for row in items}
    assert by_sku["SKU-1"]["name"] == "New name"
    assert by_sku["SKU-1"]["price"] == 237.5
    assert by_sku["SKU-1"]["observed_at"] == "2026-09-28T05:01:00Z"