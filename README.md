# EduRAG

EduRAG 是一个面向 IT 教育场景的智能问答系统，融合课程 FAQ、BM25
检索和知识库 RAG，并提供 FastAPI 与 Vue 3 前后端应用。

## 项目结构

- `integrated_qa_system/base`：配置和日志基础模块
- `integrated_qa_system/rag_qa`：文档处理、向量检索和 BERT 查询分类
- `integrated_qa_system/mysql_qa`：MySQL FAQ、Redis 缓存和 BM25 检索
- `integrated_qa_system/app.py`：HTTP 与 WebSocket API
- `EduRAG_WebProject`：Vue 3 学习问答前端

## 本地配置

复制 `integrated_qa_system/config.ini.example` 为
`integrated_qa_system/config.ini`，再填写 MySQL、Redis、Milvus 和
DashScope 配置。`config.ini` 只保留在本机，不会提交到仓库。

也可以使用同名大写环境变量覆盖配置，例如 `MYSQL_HOST`、
`MYSQL_PORT`、`DASHSCOPE_API_KEY` 和 `M3_MODEL_PATH`。

## 启动

```powershell
pip install -r integrated_qa_system/requirements.txt
python -m uvicorn integrated_qa_system.app:app --host 127.0.0.1 --port 8080
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
