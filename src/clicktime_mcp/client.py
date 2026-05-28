import httpx
from typing import Any, Optional

from clicktime_mcp.config import API_TOKEN, API_BASE_URL


class ClickTimeError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"ClickTime API error {status_code}: {message}")


class ClickTimeClient:
    """Async HTTP client for the ClickTime REST API v2."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(
            base_url=API_BASE_URL,
            headers={
                "Authorization": f"Token {API_TOKEN}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    def _api_error_message(self, response: httpx.Response) -> str:
        """Extract human-readable error from ClickTime's JSON:API error envelope."""
        try:
            body = response.json()
            errors = body.get("errors") or []
            if errors and errors[0].get("Message"):
                return errors[0]["Message"]
        except Exception:
            pass
        return response.text[:300]

    async def _raise_for_status(self, response: httpx.Response) -> Any:
        if response.status_code == 401:
            raise ClickTimeError(401, "Invalid or expired API token.")
        if response.status_code == 403:
            raise ClickTimeError(403, f"Access denied — {self._api_error_message(response)}")
        if response.status_code == 404:
            raise ClickTimeError(404, "Resource not found.")
        if response.status_code == 429:
            raise ClickTimeError(429, "Rate limit exceeded. Wait a few seconds and retry.")
        if not response.is_success:
            raise ClickTimeError(response.status_code, self._api_error_message(response))
        return response.json() if response.content else None

    async def get(self, path: str, params: Optional[dict] = None) -> Any:
        response = await self._http.get(path, params=params)
        return await self._raise_for_status(response)

    async def post(self, path: str, data: Optional[dict] = None) -> Any:
        response = await self._http.post(path, json=data or {})
        return await self._raise_for_status(response)

    async def put(self, path: str, data: dict) -> Any:
        response = await self._http.put(path, json=data)
        return await self._raise_for_status(response)

    async def delete(self, path: str) -> Any:
        response = await self._http.delete(path)
        return await self._raise_for_status(response)

    async def get_all(self, path: str, params: Optional[dict] = None) -> list:
        """Fetch all pages of a paginated endpoint using offset/limit.

        ClickTime wraps collections in a lowercase 'data' key and provides
        pagination info under 'page.count'.
        """
        params = dict(params or {})
        params.setdefault("limit", 200)
        params["offset"] = 0
        results: list = []

        while True:
            response = await self.get(path, params=params)
            page_data = response.get("data", []) if isinstance(response, dict) else (response or [])

            # Single-resource endpoint — wrap and return
            if isinstance(page_data, dict):
                return [page_data] if page_data else []

            results.extend(page_data)

            # Use page.count when available for accurate termination
            page_meta = response.get("page", {}) if isinstance(response, dict) else {}
            total = page_meta.get("count")
            if total is not None:
                if len(results) >= total:
                    break
            else:
                if len(page_data) < params["limit"]:
                    break

            params["offset"] += params["limit"]

        return results

    async def close(self) -> None:
        await self._http.aclose()
