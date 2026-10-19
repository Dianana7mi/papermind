import asyncio

import httpx

from app.core.config import settings


async def public_work(openalex_id: str):
    # Only a validated work ID is appended to a fixed host. No user URL is fetched.
    work_id = openalex_id.rsplit("/", 1)[-1]
    import re

    if not re.fullmatch(r"W\d{1,20}", work_id):
        raise ValueError("Invalid OpenAlex work ID")
    params = (
        {"api_key": settings().openalex_api_key.get_secret_value()} if settings().openalex_api_key else {}
    )
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        for attempt in range(3):
            response = await client.get(f"https://api.openalex.org/works/{work_id}", params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
            response.raise_for_status()
            work = response.json()
            return {
                "external_id": work["id"],
                "title": work.get("title"),
                "doi": work.get("doi"),
                "year": work.get("publication_year"),
                "authors": [a.get("author", {}).get("display_name") for a in work.get("authorships", [])],
                "landing_page": (work.get("primary_location") or {}).get("landing_page_url"),
                "content_scope": "metadata_only",
                "indexed": False,
            }
    raise RuntimeError("Public work unavailable")


async def public_search(query: str, year_from: int | None, year_to: int | None, page: int):
    params: dict = {"search": query, "per-page": 10, "page": page}
    filters = []
    if year_from:
        filters.append(f"from_publication_date:{year_from}-01-01")
    if year_to:
        filters.append(f"to_publication_date:{year_to}-12-31")
    if filters:
        params["filter"] = ",".join(filters)
    if settings().openalex_api_key:
        params["api_key"] = settings().openalex_api_key.get_secret_value()
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        for attempt in range(3):
            response = await client.get("https://api.openalex.org/works", params=params)
            if response.status_code == 429 or response.status_code >= 500:
                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
            response.raise_for_status()
            items, seen = [], set()
            for work in response.json().get("results", []):
                key = work.get("doi") or work["id"]
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    {
                        "id": work["id"],
                        "title": work.get("title"),
                        "doi": work.get("doi"),
                        "year": work.get("publication_year"),
                        "authors": [
                            a.get("author", {}).get("display_name") for a in work.get("authorships", [])
                        ],
                        "landing_page": (work.get("primary_location") or {}).get("landing_page_url"),
                        "open_access": work.get("open_access"),
                        "content_scope": "metadata_only",
                        "indexed": False,
                    }
                )
            return {"items": items, "page": page, "total": response.json().get("meta", {}).get("count", 0)}
    raise RuntimeError("Public search unavailable")
