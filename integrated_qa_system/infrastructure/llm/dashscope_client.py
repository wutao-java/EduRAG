import logging

from openai import OpenAI

logger = logging.getLogger(__name__)


class DashScopeClient:
    def __init__(self, api_key, base_url, model, client=None):
        self.model = model
        self.client = client or OpenAI(api_key=api_key, base_url=base_url)

    def complete(self, prompt, temperature=None):
        return "".join(self.stream(prompt, temperature=temperature))

    def stream(self, prompt, temperature=None):
        try:
            request = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "你是一个有用的助手"},
                    {"role": "user", "content": prompt},
                ],
                "timeout": 30,
                "stream": True,
            }
            if temperature is not None:
                request["temperature"] = temperature
            completions = self.client.chat.completions.create(**request)
            for chunk in completions:
                choices = getattr(chunk, "choices", None)
                if not choices:
                    continue
                delta = getattr(choices[0], "delta", None)
                content = getattr(delta, "content", None)
                if content:
                    yield content
        except Exception:
            logger.exception("调用 DashScope API 失败")
            raise

    def close(self):
        close = getattr(self.client, "close", None)
        if callable(close):
            close()
