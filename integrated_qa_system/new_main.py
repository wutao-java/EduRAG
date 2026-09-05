"""兼容旧模块名；集成问答系统的实现已归并到 main.py。"""

if __package__:
    from .main import IntegratedQASystem, main
else:
    from main import IntegratedQASystem, main

__all__ = ["IntegratedQASystem", "main"]


if __name__ == "__main__":
    main()
