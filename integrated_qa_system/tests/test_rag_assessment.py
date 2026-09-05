# -*- coding: utf-8 -*-
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "rag_qa"
    / "rag_assesmet"
    / "rag_as.py"
)
MODULE_SPEC = importlib.util.spec_from_file_location("rag_assessment", MODULE_PATH)
MODULE = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(MODULE)


class RagAssessmentTest(unittest.TestCase):
    def test_build_llm_rejects_missing_api_key(self):
        config = SimpleNamespace(
            LLM_MODEL="qwen-plus",
            DASHSCOPE_API_KEY=" ",
            DASHSCOPE_BASE_URL=(
                "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
        )

        with self.assertRaisesRegex(ValueError, "DASHSCOPE_API_KEY"):
            MODULE.build_llm(config)

    def test_build_llm_uses_dashscope_config(self):
        config = SimpleNamespace(
            LLM_MODEL="qwen-plus",
            DASHSCOPE_API_KEY="test-key",
            DASHSCOPE_BASE_URL=(
                "https://dashscope.aliyuncs.com/compatible-mode/v1"
            ),
        )

        llm = MODULE.build_llm(config)

        self.assertEqual("qwen-plus", llm.model_name)
        self.assertEqual(
            config.DASHSCOPE_BASE_URL,
            llm.openai_api_base,
        )

    def test_resolve_embedding_model_path_accepts_model_weights(self):
        with TemporaryDirectory() as model_dir:
            model_path = Path(model_dir)
            (model_path / "config.json").touch()
            (model_path / "model.safetensors").touch()
            config = SimpleNamespace(M3_MODEL_PATH=str(model_path))

            resolved_path = MODULE.resolve_embedding_model_path(config)

            self.assertEqual(model_path.resolve(), resolved_path)

    def test_resolve_embedding_model_path_rejects_missing_weights(self):
        with TemporaryDirectory() as model_dir:
            config = SimpleNamespace(M3_MODEL_PATH=model_dir)

            with self.assertRaisesRegex(
                FileNotFoundError,
                "model.safetensors.*pytorch_model.bin",
            ):
                MODULE.resolve_embedding_model_path(config)


if __name__ == "__main__":
    unittest.main()
