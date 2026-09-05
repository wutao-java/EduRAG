import unittest
from types import SimpleNamespace

from integrated_qa_system.infrastructure.llm import DashScopeClient


class FakeCompletions:
    def __init__(self):
        self.request = None

    def create(self, **request):
        self.request = request
        delta = SimpleNamespace(content="回答")
        return [SimpleNamespace(choices=[SimpleNamespace(delta=delta)])]


class DashScopeClientTest(unittest.TestCase):
    def test_supports_deterministic_completion_for_strategy_planning(self):
        completions = FakeCompletions()
        openai_client = SimpleNamespace(
            chat=SimpleNamespace(completions=completions)
        )
        client = DashScopeClient(
            api_key="key",
            base_url="https://example.com",
            model="model",
            client=openai_client,
        )

        answer = client.complete("prompt", temperature=0)

        self.assertEqual("回答", answer)
        self.assertEqual(0, completions.request["temperature"])
        self.assertTrue(completions.request["stream"])


if __name__ == "__main__":
    unittest.main()
