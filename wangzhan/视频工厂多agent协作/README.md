# 视频工厂多 Agent 协作办公室

这个目录是在 `OpenClaw-bot-review` 的像素办公室思路上，为百骑谱视频工厂做的一个独立多 Agent 控制台。  
它不会破坏原来的 `视频工厂` 功能，而是在外面增加一层“Codex API + DAG 调度 + 像素办公室可视化”。

## 1. 它解决什么问题

原视频工厂是线性工作流为主：内容输入、剧本、分镜、关键帧、视频、配音/字幕、合成、输出。  
这个项目把它拆成多个 Agent：

1. 总导演：拆解任务和并行策略
2. 参考分析：读取参考素材、RAG 马库和风格约束
3. 剧本 Agent：生成中文口播脚本
4. 分镜 Agent：拆镜头、动作、首尾帧意图
5. 关键帧 Agent：生成首尾帧提示词和连续性约束
6. 配音 Agent：保证普通话口播和声音节奏
7. 字幕 Agent：生成短句字幕和对齐策略
8. 视频 Agent：按片段并行生成 Veo/视频提示词
9. 合成 Agent：规划 FFmpeg 拼接、配音、字幕和下载
10. 质检 Agent：检查无配音、尾帧静止、字幕错位、照搬模板
11. 发布 Agent：整理交付包，可选交给原视频工厂

并行策略：

- 总导演完成后，参考分析和剧本可以并行。
- 分镜完成后，关键帧、配音、字幕可以并行。
- 视频 Agent 内部会把多个片段拆成子 Agent 并行。
- 合成只等待视频、配音、字幕三路产物。

## 2. 目录结构

```text
视频工厂多agent协作/
  app/                       Next.js 页面和 API
  lib/                       Agent 定义、Codex API、调度器、视频工厂连接器
  openclaw-source/           原 OpenClaw 项目源码参考，不参与本项目构建
  .env.example               配置模板
  README.md
```

## 3. 启动

```bash
cd 视频工厂多agent协作
npm install
npm run dev
```

打开：

```text
http://localhost:3000
```

如果 3000 被占用：

```bash
npm run dev -- -p 3001
```

## 4. Codex API 配置

复制 `.env.example` 为 `.env.local`：

```bash
copy .env.example .env.local
```

填写：

```env
CODEX_API_KEY=你的OpenAI或中转站Key
CODEX_BASE_URL=https://api.openai.com/v1
CODEX_MODEL=gpt-5.3-codex
```

如果你的中转站模型名不是 `gpt-5.3-codex`，直接改成中转站支持的模型名。  
不填 `CODEX_API_KEY` 时，项目会自动进入模拟模式，仍然能展示多 Agent 调度和像素办公室。

## 5. 和原视频工厂怎么连接

当前默认先做“多 Agent 预生产”：输出剧本、分镜、关键帧策略、视频提示词、质检结果和可交付 Payload。  
后续可以把这个 Payload 交给原视频工厂的：

```text
POST /api/v1/video/workflow/tasks
POST /api/v1/video/workflow/tasks/{task_id}/run
```

配置项：

```env
VIDEO_FACTORY_BASE_URL=http://127.0.0.1:8000/api/v1/video/workflow
VIDEO_FACTORY_ACCESS_TOKEN=你的网页登录token
```

注意：如果原站需要登录态，`VIDEO_FACTORY_ACCESS_TOKEN` 必须填真实 token；否则本项目只生成交付包，不直接提交任务。

## 6. 后续最值得继续做的点

1. 把原视频工厂每个节点拆成真实远程工具，让 Agent 不只是生成计划，而是真正调用节点。
2. 为关键帧和 Veo 片段加 Redis 队列，限制并发，避免 API 被限流。
3. 把质检 Agent 接入 ffprobe/抽帧/ASR，自动发现“无配音、尾帧静止、字幕不对齐”。
4. 把像素办公室里的 Agent 状态写回原视频工厂画布，让用户在原页面也能看到并行协作。
5. 给批量 3/5/10 条视频做任务队列，失败可跳过或重试某条。

## 7. OpenClaw 项目参考

已拉取到：

```text
openclaw-source/
```

主要参考：

- `lib/pixel-office/agentBridge.ts`：Agent 状态投射到像素办公室
- `app/api/agent-activity/route.ts`：读取 Agent 活动并返回统一数据
- `app/pixel-office/`：像素办公室页面结构

本项目没有直接修改 OpenClaw 源码，而是保留它作为参考，另外做了适配视频工厂的轻量实现。
