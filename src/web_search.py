"""DuckDuckGo web search module (free, no API key required)."""

from ddgs import DDGS


class WebSearch:
    """Web search using DuckDuckGo."""

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.max_results = cfg.get("max_results", 5)
        self.region = cfg.get("region", "us-en")

    def search(self, query: str, max_results: int | None = None) -> list[dict]:
        """Search DuckDuckGo. Returns list of {title, href, body}."""
        n = max_results or self.max_results
        try:
            results = list(DDGS().text(query, region=self.region, max_results=n))
        except Exception:
            results = []
        return results

    def search_and_format(self, query: str, max_results: int | None = None) -> str:
        """Search and return formatted string for LLM context."""
        results = self.search(query, max_results)
        if not results:
            return "No search results found."

        lines = []
        for i, r in enumerate(results, 1):
            lines.append(
                f"[{i}] {r.get('title', 'No title')}\n"
                f"    URL: {r.get('href', 'N/A')}\n"
                f"    Snippet: {r.get('body', 'No description')}"
            )
        return "\n\n".join(lines)

    def search_news(self, query: str, max_results: int | None = None) -> list[dict]:
        """Search DuckDuckGo news."""
        n = max_results or self.max_results
        try:
            results = list(DDGS().news(query, region=self.region, max_results=n))
        except Exception:
            results = []
        return results
