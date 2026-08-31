# -*- coding: utf-8 -*-
class FAQSuggestionService:
    CACHE_KEY = "faq:suggestions:v1"
    CACHE_TTL_SECONDS = 300

    def __init__(self, redis_client, mysql_client, limit=20):
        self.redis_client = redis_client
        self.mysql_client = mysql_client
        self.limit = limit

    def query(self):
        cached_suggestions = self._normalize(
            self.redis_client.get_data(self.CACHE_KEY)
        )
        if cached_suggestions:
            return cached_suggestions

        faq_pairs = self.mysql_client.fetch_faq_pairs(limit=self.limit)
        suggestions = self._normalize(
            pair.get("question")
            for pair in faq_pairs
            if isinstance(pair, dict)
        )
        if suggestions:
            self.redis_client.set_data(
                self.CACHE_KEY,
                suggestions,
                expire_seconds=self.CACHE_TTL_SECONDS,
            )
        return suggestions

    @staticmethod
    def _normalize(suggestions):
        if not suggestions:
            return []

        unique_suggestions = []
        seen = set()
        for suggestion in suggestions:
            if not isinstance(suggestion, str):
                continue
            normalized_suggestion = suggestion.strip()
            if not normalized_suggestion or normalized_suggestion in seen:
                continue
            seen.add(normalized_suggestion)
            unique_suggestions.append(normalized_suggestion)
        return unique_suggestions
