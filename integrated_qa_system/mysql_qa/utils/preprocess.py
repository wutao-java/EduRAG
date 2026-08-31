# -*-coding:utf-8-*-
# utils/preprocess.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入分词库
import jieba
# 导入日志
from base import logger

def preprocess_text(text):
    # 预处理文本
    logger.info("开始预处理文本")
    try:
        # 分词并转换为小写，过滤空白和纯标点，避免 BM25 被引号等符号干扰。
        return [
            token
            for token in jieba.lcut(text.lower())
            if any(character.isalnum() for character in token)
        ]
    except AttributeError as e:
        # 记录预处理失败
        logger.error(f"文本预处理失败: {e}")
        # 返回空列表
        return []
