import argparse
import sys

from .commands import run_chat, run_faq, run_index


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="EduRAG 统一进程入口")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="启动 FastAPI 服务")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8000)
    serve_parser.add_argument("--reload", action="store_true")

    subparsers.add_parser("chat", help="启动交互式集成问答")

    index_parser = subparsers.add_parser("index", help="处理文档并写入向量库")
    index_parser.add_argument("--data-dir", default="data")

    subparsers.add_parser("faq", help="启动 MySQL FAQ 调试终端")
    return parser


def run_server(host: str, port: int, reload: bool) -> None:
    import uvicorn

    uvicorn.run(
        "integrated_qa_system.web.app:app",
        host=host,
        port=port,
        reload=reload,
    )


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        arguments = ["serve"]

    args = create_parser().parse_args(arguments)
    if args.command == "serve":
        run_server(args.host, args.port, args.reload)
    elif args.command == "chat":
        run_chat()
    elif args.command == "index":
        run_index(args.data_dir)
    elif args.command == "faq":
        run_faq()


if __name__ == "__main__":
    main()
