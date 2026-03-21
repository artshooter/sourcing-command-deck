# Sourcing Command Deck

一个可本机运行的真实版本网页入口：
- 上传企划 `.xlsx`
- 调用现有 `run_auto_batch_workflow.py`
- 轮询任务状态
- 输出视觉化结果页

## 启动

```bash
cd /root/.openclaw/workspace
python3 apps/sourcing-web/server.py
```

默认地址：

```bash
http://127.0.0.1:8765
```

## 默认依赖

这个版本故意不依赖 Flask/FastAPI，直接用 Python 标准库，适合当前 Python 3.6 环境。

## 前置条件

1. `secrets/1688-cookie.txt` 存在
2. 企划文件为 `.xlsx`
3. parser 能从模板中识别出至少一个 item

## 接口

- `GET /api/health`
- `GET /api/template-spec`
- `POST /api/jobs` （multipart: `planning_file`, `max_items`, `queries`, `pages`, `top_k`, `cookie_path`）
- `GET /api/jobs/<job_id>`

## 目录

- `static/`：前端页面
- `runs/<job_id>/`：每次任务的上传文件、解析结果、dashboard JSON
