# EduRAG WebProject

基于 Vue 3 和 Vite 的 EduRAG 学习问答前端，界面迁移自原型目录 `integrated_qa_system/static`，已接入 FastAPI REST 与 WebSocket 接口。

## 启动后端

```powershell
cd D:\EduRAG\EduRAG_HUB
python -m uvicorn integrated_qa_system.app:app --host 127.0.0.1 --port 8000
```

## 启动前端

```powershell
cd D:\EduRAG\EduRAG_HUB\EduRAG_WebProject
npm install
npm run dev
```

浏览器访问 `http://127.0.0.1:5173`。开发服务器默认将 `/api` 和 WebSocket 请求代理到 `http://127.0.0.1:8000`。

## 验证命令

```powershell
npm test
npm run build
```

前后端分开部署时，复制 `.env.example` 为 `.env.production`，填写实际 API 和 WebSocket 地址后再执行构建。
