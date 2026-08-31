# -*-coding:utf-8-*-
from contextlib import contextmanager
import sys
from pathlib import Path
import threading

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pymysql

from base import Config, logger

class MySQLClient:
    def __init__(self):
        # 初始化日志
        self.logger = logger
        self._lock = threading.RLock()
        try:
            # 连接 MySQL 数据库
            config = Config()
            self.connection = pymysql.connect(
                host=config.MYSQL_HOST,
                port=config.MYSQL_PORT,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                database=config.MYSQL_DATABASE
            )
            # 记录连接成功
            self.logger.info("MySQL 连接成功")
        except pymysql.MySQLError as e:
            # 记录连接失败
            self.logger.error(f"MySQL 连接失败: {e}")
            raise

    @contextmanager
    def cursor_context(self, commit=False):
        """串行执行数据库操作，并在连接失效时自动重连。"""
        with self._lock:
            self.connection.ping(reconnect=True)
            cursor = self.connection.cursor()
            try:
                yield cursor
                if commit:
                    self.connection.commit()
            except Exception:
                if commit:
                    try:
                        self.connection.rollback()
                    except Exception as rollback_error:
                        self.logger.warning("数据库回滚失败: %s", rollback_error)
                raise
            finally:
                cursor.close()


    def create_table(self):
        create_table_query = '''
        CREATE TABLE IF NOT EXISTS jpkb (
            id INT AUTO_INCREMENT PRIMARY KEY,
            subject_name VARCHAR(20),
            question VARCHAR(1000),
            answer VARCHAR(1000))
        '''
        try:
            with self.cursor_context(commit=True) as cursor:
                cursor.execute(create_table_query)
            self.logger.info("表创建成功")
        except pymysql.MySQLError as e:
            self.logger.error(f"表创建失败: {e}")
            raise

    def insert_data(self, csv_path):
        try:
            data = pd.read_csv(csv_path)
            print(data.head())
            with self.cursor_context(commit=True) as cursor:
                for _, row in data.iterrows():
                    insert_query = "INSERT INTO jpkb (subject_name, question, answer) VALUES (%s, %s, %s)"
                    cursor.execute(insert_query, (row["学科名称"], row["问题"],row["答案"]))
            self.logger.info("Mysql数据插入成功")
        except Exception as e:
            self.logger.error(f'Mysql数据插入失败:{e}')
            raise

    def fetch_questions(self):
        # 获取所有问题
        try:
            # 执行查询
            with self.cursor_context() as cursor:
                cursor.execute("SELECT question FROM jpkb")
                # 获取结果
                #   # results:(('static静态方法使用非静态变量',), ...)
                results = cursor.fetchall()
            # 记录获取成功
            self.logger.info("成功获取问题")
            # 返回结果
            return results
        except pymysql.MySQLError as e:
            # 记录查询失败
            self.logger.error(f"查询失败: {e}")
            # 返回空列表
            return []

    def fetch_faq_pairs(self, limit=2):
        """获取“试着问”使用的 FAQ 问答对。"""

        try:
            with self.cursor_context() as cursor:
                cursor.execute(
                    """
                    SELECT question, answer
                    FROM jpkb
                    WHERE question IS NOT NULL AND TRIM(question) <> ''
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (limit,),
                )
                results = cursor.fetchall()
            return [
                {"question": question, "answer": answer}
                for question, answer in results
            ]
        except pymysql.MySQLError as e:
            self.logger.error(f"FAQ 问答对查询失败: {e}")
            return []

    def fetch_answer(self, question):
        # 获取指定问题的答案
        try:
            # 执行查询
            with self.cursor_context() as cursor:
                cursor.execute("SELECT answer FROM jpkb WHERE question=%s", (question,))
                # 获取结果
                result = cursor.fetchone()
            print(f'result--》{result}')
            # 返回答案或 None
            return result[0] if result else None
        except pymysql.MySQLError as e:
            # 记录答案获取失败
            self.logger.error(f"答案获取失败: {e}")
            # 返回 None
            return None

    def close(self):
        # 关闭数据库连接
        try:
            # 关闭连接
            with self._lock:
                self.connection.close()
            # 记录关闭成功
            self.logger.info("MySQL 连接已关闭")
        except pymysql.MySQLError as e:
            # 记录关闭失败
            self.logger.error(f"关闭连接失败: {e}")
if __name__ == '__main__':
    mysql_client = MySQLClient()
    mysql_client.create_table()
    mysql_client.insert_data("../data/JP学科知识问答.csv")
    print(mysql_client.fetch_questions())
