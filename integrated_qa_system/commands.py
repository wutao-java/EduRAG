import time
import uuid
from pathlib import Path


def run_chat() -> None:
    from .application.system import IntegratedQASystem
    from .base import logger

    qa_system = IntegratedQASystem()
    session_id = str(uuid.uuid4())
    print("\n欢迎使用集成问答系统！")
    print(f"会话ID: {session_id}")
    print(f"支持的学科类别：{qa_system.config.VALID_SOURCES}")
    print("输入查询进行问答，输入 'exit' 退出。")

    try:
        while True:
            query = input("\n输入查询: ").strip()
            if query.lower() == "exit":
                print("再见！")
                break

            source_filter = input(
                f"请输入学科类别 ({'/'.join(qa_system.config.VALID_SOURCES)}) "
                "(直接回车默认不过滤): "
            ).strip()
            if source_filter and source_filter not in qa_system.config.VALID_SOURCES:
                logger.warning("无效的学科类别 '%s'，将不过滤", source_filter)
                source_filter = None

            print("\n答案: ", end="", flush=True)
            for token, is_complete in qa_system.query(
                query,
                source_filter=source_filter,
                session_id=session_id,
            ):
                if token:
                    print(token, end="", flush=True)
                if is_complete:
                    print()
                    break

            print("\n最近对话历史:")
            for index, entry in enumerate(
                qa_system.get_session_history(session_id),
                start=1,
            ):
                print(
                    f"{index}. 问: {entry['question']}\n"
                    f"   答: {entry['answer']}"
                )
    except Exception as exception:
        logger.exception("系统错误")
        print(f"发生错误: {exception}")
    finally:
        qa_system.close()


def run_index(data_directory: str = "data") -> None:
    from .base import Config, logger
    from .rag_qa import VectorStore
    from .rag_qa.core.document_processor import process_documents

    config = Config()
    vector_store = VectorStore(
        collection_name=config.MILVUS_COLLECTION_NAME,
        host=config.MILVUS_HOST,
        port=config.MILVUS_PORT,
        database=config.MILVUS_DATABASE_NAME,
    )
    total_chunks = 0

    for source in config.VALID_SOURCES:
        source_directory = Path(data_directory) / f"{source}_data"
        if not source_directory.exists():
            logger.warning("目录 %s 不存在，跳过处理", source_directory)
            continue

        chunks = process_documents(
            str(source_directory),
            config.PARENT_CHUNK_SIZE,
            config.CHILD_CHUNK_SIZE,
            config.CHUNK_OVERLAP,
        )
        if chunks:
            vector_store.add_documents(chunks)
            total_chunks += len(chunks)
            logger.info("目录 %s 添加了 %s 个文档块", source_directory, len(chunks))

    logger.info("数据处理完成，共添加 %s 个文档块", total_chunks)


def run_faq() -> None:
    from .base import logger
    from .mysql_qa import BM25Search, MySQLClient, RedisClient

    mysql_client = MySQLClient()
    redis_client = None
    try:
        redis_client = RedisClient()
        faq_search = BM25Search(redis_client, mysql_client)
        print("\n欢迎使用 MySQL FAQ 调试终端！")
        print("输入查询进行检索，输入 'exit' 退出。")

        while True:
            query = input("\n输入查询: ").strip()
            if query.lower() == "exit":
                print("再见！")
                break

            start_time = time.perf_counter()
            answer, _ = faq_search.search(query, threshold=0.85)
            print(f"\n答案: {answer or 'SQL未找到答案'}")
            logger.info("FAQ 查询处理耗时 %.2fs", time.perf_counter() - start_time)
    finally:
        mysql_client.close()
        if redis_client is not None:
            redis_client.client.close()
