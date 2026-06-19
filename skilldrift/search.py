from __future__ import annotations

import logging
from typing import Any

import requests

from skilldrift.config import Settings, get_settings

logger = logging.getLogger(__name__)


class SearchUnavailable(RuntimeError):
    pass


class SolrSearch:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.session = requests.Session()

    def ping(self) -> bool:
        try:
            response = self.session.get(
                f"{self.settings.solr_url}/admin/ping",
                timeout=self.settings.solr_timeout_seconds,
            )
            return response.ok
        except requests.RequestException:
            return False

    def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        try:
            response = self.session.get(
                f"{self.settings.solr_url}/select",
                params={
                    "q": query,
                    "q.op": "AND",
                    "df": "_text_",
                    "rows": limit,
                    "wt": "json",
                    "fl": "id,title,company,tags,description,snapshot_date,source,source_url,score",
                },
                timeout=self.settings.solr_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()["response"]
            return {"total": payload["numFound"], "items": payload["docs"]}
        except (requests.RequestException, KeyError, ValueError) as exc:
            logger.exception("Solr search failed")
            raise SearchUnavailable("Search service is temporarily unavailable") from exc
