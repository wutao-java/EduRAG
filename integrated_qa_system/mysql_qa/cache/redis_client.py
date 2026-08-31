# -*-coding:utf-8-*-
# cache/redis_client.py
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 导入 Redis 客户端
import redis
# 导入 JSON 处理
import json
# 导入配置和日志
from base import Config, logger


class RedisClient:
    ANSWER_CACHE_PREFIX = "answer:v2:"

    def __init__(self):
        # 初始化日志
        self.logger = logger
        try:
            # 连接 Redis
            self.client = redis.StrictRedis(
                host=Config().REDIS_HOST,
                port=Config().REDIS_PORT,
                password=Config().REDIS_PASSWORD,
                db=Config().REDIS_DB,
                decode_responses=True
            )
            # 记录连接成功
            self.logger.info("Redis 连接成功")
        except redis.RedisError as e:
            # 记录连接失败
            self.logger.error(f"Redis 连接失败: {e}")
            raise

    def set_data(self, key, value, expire_seconds=None):
        # 存储数据到 Redis
        try:
            # 存储 JSON 数据
            self.client.set(
                key,
                json.dumps(value),
                ex=expire_seconds,
            )
            # 记录存储成功
            self.logger.info(f"存储数据到 Redis: {key}")
        except redis.RedisError as e:
            # 记录存储失败
            self.logger.error(f"Redis 存储失败: {e}")

    def get_data(self, key):
        # 从 Redis 获取数据
        try:
            # 获取数据
            data = self.client.get(key)
            # 返回解析后的 JSON 数据或 None
            return json.loads(data) if data else None
        except redis.RedisError as e:
            # 记录获取失败
            self.logger.error(f"Redis 获取失败: {e}")
            # 返回 None
            return None

    def set_answer(self, query, answer):
        self.set_data(f"{self.ANSWER_CACHE_PREFIX}{query}", answer)

    def get_answer(self, query):
        # 获取查询的缓存答案
        try:
            # 从 Redis 获取答案
            answer = self.client.get(f"{self.ANSWER_CACHE_PREFIX}{query}")
            if answer:
                # 记录获取成功
                self.logger.info(f"从 Redis 获取答案: {query}")
                # set_data 使用 JSON 序列化写入，读取时需要还原原始字符串。
                try:
                    return json.loads(answer)
                except json.JSONDecodeError:
                    # 兼容历史上直接写入 Redis 的纯文本答案。
                    return answer
            # 返回 None
            return None
        except redis.RedisError as e:
            # 记录查询失败
            self.logger.error(f"Redis 查询失败: {e}")
            # 返回 None
            return None
if __name__ == '__main__':
    redcli = RedisClient()
    print(redcli)
