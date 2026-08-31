# -*-coding:utf-8-*-
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from base import Config

# 导入ragas库的evaluate函数，用于执行RAG评估
from ragas import evaluate
# 导入ragas的评估指标，包括忠实度、答案相关性、上下文相关性和上下文召回率
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,  # context_relevancy(原来的写法)两者是一回事
    context_recall
)
# 导入datasets库的Dataset类，用于构建RAGAS所需的数据格式
from datasets import Dataset
# 导入聊天模型和本地 Hugging Face 嵌入模型
from langchain_openai import ChatOpenAI
from langchain_community.embeddings import HuggingFaceEmbeddings
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
conf = Config()


def main():
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
    llm = ChatOpenAI(
        model_name=conf.LLM_MODEL,
        api_key=conf.DASHSCOPE_API_KEY,
        base_url=conf.DASHSCOPE_BASE_URL)

    embedding_model_path = Path(__file__).resolve().parents[1] / "models" / "bge-m3"
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
