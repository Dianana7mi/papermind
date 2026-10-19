from conftest import account


async def test_metadata_import_is_scoped_idempotent_and_not_indexed(client, auth, library, monkeypatch):
    import app.api.routes as routes

    calls = []

    async def test_work(work_id):
        calls.append(work_id)
        return {
            "external_id": work_id,
            "title": "Explicit synthetic metadata test",
            "content_scope": "metadata_only",
            "indexed": False,
        }

    monkeypatch.setattr(routes, "public_work", test_work)
    body = {"library_id": library, "openalex_id": "W123456"}
    first = await client.post("/api/v1/public/import", headers=auth, json=body)
    assert first.status_code == 201, first.text
    duplicate = await client.post("/api/v1/public/import", headers=auth, json=body)
    assert duplicate.json()["duplicate"] is True
    assert len(calls) == 1
    assert first.json()["metadata"]["indexed"] is False
    assert (await client.get("/api/v1/papers", headers=auth, params={"library_id": library})).json()[
        "items"
    ] == []
    bob = await account(client, "bob@example.org")
    assert (
        await client.get("/api/v1/public/references", headers=bob, params={"library_id": library})
    ).status_code == 404
    assert (
        await client.delete(f"/api/v1/public/references/{first.json()['id']}", headers=bob)
    ).status_code == 404
    assert (await client.delete(f"/api/v1/libraries/{library}", headers=auth)).status_code == 204


async def test_metadata_import_rejects_arbitrary_urls(client, auth, library):
    for url in ("http://127.0.0.1/admin", "https://openalex.org/W1/../../users", "W1?api_key=evil"):
        result = await client.post(
            "/api/v1/public/import", headers=auth, json={"library_id": library, "openalex_id": url}
        )
        assert result.status_code == 422
