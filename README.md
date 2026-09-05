# EduRAG

EduRAG 是一个面向 IT 教育场景的智能问答系统，融合课程 FAQ、BM25、
知识库 RAG 和 LangGraph Agent，并提供 FastAPI 与 Vue 3 前后端应用。

## 项目结构

- `integrated_qa_system/base`：配置和日志基础模块
- `integrated_qa_system/application`：问答用例、系统门面和低成本 FAQ 分流
- `integrated_qa_system/agent`：LangGraph 状态、编排图和 Agent 工具
- `integrated_qa_system/conversation`：会话服务和 MySQL 持久化仓储
- `integrated_qa_system/infrastructure`：DashScope 等外部系统适配器
- `integrated_qa_system/rag_qa`：文档处理、检索规划、证据检索和答案生成
- `integrated_qa_system/mysql_qa`：MySQL FAQ、Redis 缓存和 BM25 检索
- `integrated_qa_system/web/app.py`：FastAPI 工厂、生命周期和全局异常边界
- `integrated_qa_system/web/routers`：健康检查、会话、问答和系统接口
- `integrated_qa_system/bootstrap.py`：运行时依赖的唯一组合根
- `integrated_qa_system/main.py`：唯一后端进程入口
- `integrated_qa_system/commands.py`：交互问答、文档索引和 FAQ 调试命令
- `EduRAG_WebProject`：Vue 3 学习问答前端

查询首先匹配问候语和高置信度 FAQ。未命中时进入 Agent，依次执行查询规划、
知识库检索工具和答案生成。Agent 只依赖业务服务，不直接访问 MySQL、Redis
或 Milvus；会话历史仍由 MySQL 保存，不与 LangGraph 状态重复持久化。

`/health/live` 用于进程存活检查，`/health/ready` 用于确认问答系统已经完成
生命周期初始化。原有 `/health` 接口继续保留。

## 本地配置

在 `integrated_qa_system/config.ini` 中填写 MySQL、Redis、Milvus 和
DashScope 配置。该文件只保留在本机，不会提交到仓库。

也可以使用同名大写环境变量覆盖配置，例如 `MYSQL_HOST`、
`MYSQL_PORT`、`DASHSCOPE_API_KEY` 和 `M3_MODEL_PATH`。

## 启动

```powershell
pip install -r integrated_qa_system/requirements.txt
python -m integrated_qa_system.main serve --host 127.0.0.1 --port 8000
```

本地使用默认地址和端口时，也可以直接运行
`python -m integrated_qa_system.main`。其他后端命令仍使用同一入口：

```powershell
python -m integrated_qa_system.main chat
python -m integrated_qa_system.main index --data-dir integrated_qa_system/rag_qa/data
python -m integrated_qa_system.main faq
```

```powershell
cd EduRAG_WebProject
npm ci
npm run dev
```

## 验证

```powershell
python -m compileall -q integrated_qa_system
python -m unittest discover -s integrated_qa_system/tests -v
```

```powershell
cd EduRAG_WebProject
npm test
npm run build
```
