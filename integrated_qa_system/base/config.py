# -*- coding: utf-8 -*-
import ast
import configparser
import os

config_file = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config.ini",
)


class Config:
    def __init__(self, config_file=config_file):
        self.config = configparser.ConfigParser()
        self.config.read(config_file, encoding="utf-8")
        config_dir = os.path.dirname(os.path.abspath(config_file))

        self.MYSQL_HOST = self._get("mysql", "host", "MYSQL_HOST", "127.0.0.1")
        self.MYSQL_PORT = self._getint("mysql", "port", "MYSQL_PORT", 3306)
        self.MYSQL_USER = self._get("mysql", "user", "MYSQL_USER", "root")
        self.MYSQL_PASSWORD = self._get("mysql", "password", "MYSQL_PASSWORD", "")
        self.MYSQL_DATABASE = self._get(
            "mysql",
            "database",
            "MYSQL_DATABASE",
            "subjects_kg",
        )

        self.REDIS_HOST = self._get("redis", "host", "REDIS_HOST", "127.0.0.1")
        self.REDIS_PORT = self._getint("redis", "port", "REDIS_PORT", 6379)
        self.REDIS_PASSWORD = self._get("redis", "password", "REDIS_PASSWORD", "")
        self.REDIS_DB = self._getint("redis", "db", "REDIS_DB", 0)
        self.LOG_FILE = self._get("logger", "log_file", "LOG_FILE", "logs/app.log")

        self.MILVUS_HOST = self._get("milvus", "host", "MILVUS_HOST", "127.0.0.1")
        self.MILVUS_PORT = self._get("milvus", "port", "MILVUS_PORT", "19530")
        self.MILVUS_DATABASE_NAME = self._get(
            "milvus",
            "database_name",
            "MILVUS_DATABASE_NAME",
            "default",
        )
        self.MILVUS_COLLECTION_NAME = self._get(
            "milvus",
            "collection_name",
            "MILVUS_COLLECTION_NAME",
            "edurag",
        )

        self.LLM_MODEL = self._get("llm", "model", "LLM_MODEL", "qwen-plus")
        self.DASHSCOPE_API_KEY = self._get(
            "llm",
            "dashscope_api_key",
            "DASHSCOPE_API_KEY",
            "",
        )
        self.DASHSCOPE_BASE_URL = self._get(
            "llm",
            "dashscope_base_url",
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        self.M3_MODEL_PATH = self._model_path(
            config_dir,
            "m3_model_path",
            "M3_MODEL_PATH",
            "./rag_qa/models/bge-m3",
        )
        self.RERANKER_MODEL_PATH = self._model_path(
            config_dir,
            "reranker_model_path",
            "RERANKER_MODEL_PATH",
            "./rag_qa/models/bge-reranker-large",
        )

        self.PARENT_CHUNK_SIZE = self._getint(
            "retrieval",
            "parent_chunk_size",
            "PARENT_CHUNK_SIZE",
            1200,
        )
        self.CHILD_CHUNK_SIZE = self._getint(
            "retrieval",
            "child_chunk_size",
            "CHILD_CHUNK_SIZE",
            300,
        )
        self.CHUNK_OVERLAP = self._getint(
            "retrieval",
            "chunk_overlap",
            "CHUNK_OVERLAP",
            50,
        )
        self.RETRIEVAL_K = self._getint(
            "retrieval",
            "retrieval_k",
            "RETRIEVAL_K",
            5,
        )
        self.CANDIDATE_M = self._getint(
            "retrieval",
            "candidate_m",
            "CANDIDATE_M",
            2,
        )
        self.CUSTOMER_SERVICE_PHONE = self._get(
            "app",
            "customer_service_phone",
            "CUSTOMER_SERVICE_PHONE",
            "",
        )
        self.VALID_SOURCES = self._parse_sources(
            self._get(
                "retrieval",
                "valid_sources",
                "VALID_SOURCES",
                "['java', 'python', '运维', 'ai']",
            )
        )

    def _get(self, section, option, environment_name, fallback):
        environment_value = os.getenv(environment_name)
        if environment_value is not None:
            return environment_value
        return self.config.get(section, option, fallback=fallback)

    def _getint(self, section, option, environment_name, fallback):
        value = self._get(section, option, environment_name, str(fallback))
        return int(value)

    def _model_path(self, config_dir, option, environment_name, fallback):
        path = self._get("loca_models", option, environment_name, fallback)
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(config_dir, path))

    @staticmethod
    def _parse_sources(value):
        try:
            parsed_value = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            parsed_value = value.split(",")

        if isinstance(parsed_value, str):
            parsed_value = parsed_value.split(",")
        return [str(source).strip() for source in parsed_value if str(source).strip()]

if __name__ == '__main__':
    print(config_file)
