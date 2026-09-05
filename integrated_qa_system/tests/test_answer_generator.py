import unittest

from integrated_qa_system.rag_qa.core.answer_generator import RAGAnswerGenerator


class Document:
    def __init__(self, content):
        self.page_content = content


class RAGAnswerGeneratorTest(unittest.TestCase):
    def test_builds_prompt_from_evidence_and_history(self):
        prompts = []

        def stream_llm(prompt):
            prompts.append(prompt)
            yield "回答"

        generator = RAGAnswerGenerator(stream_llm, "12345")
        answer = generator.generate_answer(
            "当前问题",
            [Document("知识库证据")],
            history=[{"question": "上一问", "answer": "上一答"}],
            category="专业咨询",
        )

        self.assertEqual("回答", answer)
        self.assertIn("知识库证据", prompts[0])
        self.assertIn("上一问", prompts[0])
        self.assertIn("当前问题", prompts[0])

    def test_returns_safe_message_when_llm_fails(self):
        def failing_llm(prompt):
            raise RuntimeError("secret upstream detail")

        generator = RAGAnswerGenerator(failing_llm, "12345")
        answer = generator.generate_answer(
            "当前问题",
            [],
            category="专业咨询",
        )

        self.assertIn("12345", answer)
        self.assertNotIn("secret upstream detail", answer)


if __name__ == "__main__":
    unittest.main()
