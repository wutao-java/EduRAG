# -*-coding:utf-8-*-
import json
import sys
import warnings
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from base import Config

# 导入聊天模型
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
conf = Config()


def resolve_embedding_model_path(config):
    model_path = Path(config.M3_MODEL_PATH).expanduser().resolve()
    weight_files = (
        model_path / "model.safetensors",
        model_path / "pytorch_model.bin",
    )
    if not model_path.is_dir() or not any(path.is_file() for path in weight_files):
        raise FileNotFoundError(
            f"嵌入模型目录 {model_path} 缺少 model.safetensors 或 "
            "pytorch_model.bin。请下载完整模型权重，或通过 "
            "M3_MODEL_PATH 指向完整模型目录。"
        )
    return model_path


def build_llm(config):
    api_key = (config.DASHSCOPE_API_KEY or "").strip()
    if not api_key:
        raise ValueError(
            "未配置 DashScope API Key。请在 "
            "integrated_qa_system/config.ini 的 [llm] 节中填写 "
            "dashscope_api_key，或设置环境变量 DASHSCOPE_API_KEY。"
        )

    return ChatOpenAI(
        model=config.LLM_MODEL,
        api_key=api_key,
        base_url=config.DASHSCOPE_BASE_URL,
    )


def main():
    # 评估依赖只在执行评估时加载，配置预检和单元测试无需初始化整套 RAGAS。
    from datasets import Dataset
    from langchain_community.embeddings import HuggingFaceEmbeddings
    from ragas import evaluate

    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message="Importing .* from 'ragas.metrics' is deprecated.*",
            category=DeprecationWarning,
        )
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )

    llm = build_llm(conf)

    # 1. 加载生成的数据集
    data_file = Path(__file__).resolve().parent / "rag_evaluate_data.json"
    with data_file.open("r", encoding="utf-8") as file:
        data = json.load(file)

    print(f'data--》{len(data)}')
    # 2. 转换为RAGAS格式
    eval_data = {
        "question": [item["question"] for item in data],
        "answer": [item["answer"] for item in data],
        "contexts": [item["context"] for item in data],
        "ground_truth": [item["ground_truth"] for item in data]
    }
    dataset = Dataset.from_dict(eval_data)
    print(f'dataset--》{dataset}')

    # 3. 配置RAGAS评估环境
    embedding_model_path = resolve_embedding_model_path(conf)
    embeddings = HuggingFaceEmbeddings(
        model_name=str(embedding_model_path),
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True}
    )

    # 4. 执行评估
    result = evaluate(
        dataset=dataset,
        metrics=[
            faithfulness,
            answer_relevancy,
            context_precision,
            context_recall
        ],
        llm=llm,
        embeddings=embeddings
    )

    # 5. 输出评估结果
    print("RAGAS评估结果：")
    print(result)


if __name__ == "__main__":
    main()
