# NeoStore

轻量**单店** DTC 跨境独立站。单租户、单店，不做多商户 / marketplace / POS；多语言与多币种从第一天就是一等公民。

顾客端必须 SSR（SEO 是独立站的命脉），后台是独立的 SPA；两者共用一个 FastAPI 后端。

```
                    ┌──────────────────────────────┐
  浏览器  ──────────▶│ Caddy :80/:443               │
                    │  /api/*    → api:8000        │
                    │  /admin/*  → admin:80        │
                    │  其余      → storefront:3000  │
                    └──────────────────────────────┘
                              │            │
              ┌───────────────┘            └──────────────┐
              ▼                                          ▼
   ┌────────────────────┐                    ┌──────────────────────┐
   │ storefront         │                    │ admin                │
   │ Next.js 15 (SSR)   │                    │ Vite + React         │
   │ Server Component   │                    │ 只调 /api/v1/admin/* │
   │ 直连 API           │                    └──────────────────────┘
   └────────────────────┘                                │
              │                                          │
              └───────────────┬──────────────────────────┘
                              ▼
                   ┌──────────────────────┐        ┌─────────────┐
                   │ FastAPI              │        │ arq worker  │
                   │ app/api → app/domain │───────▶│ 汇率定时刷新 │
                   └──────────────────────┘        └─────────────┘
                       │            │
                 ┌─────┘            └─────┐
                 ▼                        ▼
          PostgreSQL 16              Redis 7
```

## 目录

| 路径 | 作用 |
|---|---|
| `backend/app/api/` | HTTP 层。只做参数校验、调用领域服务、事务提交 |
| `backend/app/domain/` | 领域层：`catalog` `i18n` `currency` `region` `cart` `pricing` `inventory` `order` `payment`。**不 import fastapi，不直接持有 Session** |
| `backend/app/core/` | 配置、依赖注入、统一错误处理 |
| `backend/app/db/` | 引擎、Session 工厂、Base |
| `backend/alembic/` | 迁移 |
| `storefront/` | Next.js 15 App Router 顾客端，`[locale]` 路由段 |
| `admin/` | Vite + React 管理后台，挂在 `/admin/` |
| `scripts/smoke.sh` | 端到端冒烟测试 |
| `docs/superpowers/` | 设计文档与实施计划 |

## 起服务

```bash
cp backend/.env.example backend/.env     # 至少改掉 JWT_SECRET
docker compose up --build
```

| 入口 | 地址 |
|---|---|
| 顾客端 | http://localhost:3000/zh-CN |
| 后台 | http://localhost:5173/admin/ |
| API 文档 | http://localhost:8000/docs |
| 经 Caddy | http://localhost/api/v1/... 、http://localhost/admin/ |

种子账号：`admin@neostore.local` / `admin123`（**上线前必须改**，见 RUNBOOK）。

首次启动时 `api` 容器会自己跑 `alembic upgrade head` 和 `python -m app.seed`。种子脚本是幂等的，重复执行只会补齐缺失数据。

## 本地开发（不用 Docker）

```bash
# 后端：SQLite 也能跑，无需 PostgreSQL
cd backend
python3.13 -m venv .venv && .venv/bin/pip install -e '.[dev]'
DATABASE_URL="sqlite+aiosqlite:///./dev.db" .venv/bin/python -m app.seed --create-all --skip-rates
DATABASE_URL="sqlite+aiosqlite:///./dev.db" .venv/bin/uvicorn app.main:app --reload

# 顾客端
cd storefront && npm install && npm run dev        # :3000

# 后台
cd admin && npm install && npm run dev            # :5173，/api 走 Vite 代理
```

## 常用命令

| 命令 | 作用 |
|---|---|
| `bash scripts/smoke.sh` | 全链路冒烟：下单 → 幂等 → 支付 → 后台 → 两个前端渲染 |
| `bash scripts/smoke.sh --api-only` | 只跑后端部分 |
| `node scripts/admin-check.cjs <后台地址> <订单号>` | 用真实浏览器把后台走一遍（登录 → 概览 → 各页 → 状态流转），失败即非零退出 |
| `cd backend && .venv/bin/python -m pytest` | 后端测试 |
| `cd backend && .venv/bin/ruff check .` | 后端 lint（含"domain 层禁止 import fastapi"规则） |
| `cd storefront && npm run build` | 顾客端构建 |
| `cd admin && npm run typecheck && npm run build` | 后台类型检查与构建 |
| `alembic revision --autogenerate -m "..."` | 生成迁移（在 `backend/` 下执行） |

冒烟脚本会自己挑 8010/3110/3111 三个端口；被占用时直接报错退出，不会误连别人的服务。端口可用环境变量换：`API_PORT=9010 WEB_PORT=9110 ADMIN_PORT=9111 bash scripts/smoke.sh`。

## 环境变量

**backend**（见 `backend/.env.example`）

| 变量 | 说明 |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://…`；本地可用 `sqlite+aiosqlite:///./dev.db` |
| `REDIS_URL` | arq 队列 |
| `JWT_SECRET` | **必须替换** |
| `EXCHANGE_RATE_REFRESH_HOURS` | worker 刷新间隔，最小 1 小时 |
| `DEFAULT_LOCALE` / `DEFAULT_CURRENCY` | 兜底语言与币种 |
| `ENABLE_MOCK_PAYMENTS` | 演示用支付确认接口开关，**上线必须关掉**（关掉后 `/store/orders/{n}/pay` 直接 404） |

**storefront**（见 `storefront/.env.example`）

| 变量 | 说明 |
|---|---|
| `API_BASE_URL` | **Server Component** 走这个地址，容器内用服务名 `http://api:8000` |
| `NEXT_PUBLIC_API_BASE_URL` | **浏览器**走这个地址，必须是访客机器能解析的 URL |
| `NEXT_PUBLIC_SITE_URL` | canonical / hreflang / sitemap 的绝对前缀 |
| `NEXT_PUBLIC_LOCALES` | 必须与 `locale` 表一致（middleware 在边缘跑，查不了库） |

`NEXT_PUBLIC_*` 在构建期被内联进产物，改了要重新构建。后台没有这类变量：它固定调同源的 `/api/v1`，Caddy 与 Vite 代理各自负责转发。

## 架构约束（改代码前先看）

1. `domain/` 不许 import fastapi、不许直接持有 Session；持久化走 repository 接口。ruff 的 `TID251` 规则会拦住。
2. 金额一律 `Decimal`，禁止 `float`。所有金额计算收敛到 `pricing.calculate()` 一个入口，API 层和前端都不算钱。
3. 订单行快照商品名 / SKU / 单价到 `order_line`，不回查商品表——商品改名不能改写历史订单。
4. 订单状态只能经 `order.mark_*()` 流转，每次流转写 `order_event` 审计。
5. 多语言用独立翻译表，`UNIQUE(entity_id, locale)`；回退链「请求 locale → 默认 locale → 空」在服务层处理。
6. 多币种：显式定价优先，缺失时按最新汇率换算兜底，按目标币种 `decimal_places` 取整。
7. 前端 TS 类型从 OpenAPI 生成，不手写 interface。
8. 时间戳出 API 前一律带上 UTC 偏移（`app/core/serialization.py` 的 `UtcDatetime`）。PostgreSQL 返回 aware、SQLite 返回 naive，不统一的话同一个订单在浏览器里会差一个时区；前端拿到 `+00:00` 自行转本地时间。

## 已知取舍

- **演示闭环优先**：没有真实支付网关，`/store/orders/{number}/pay` 是替代品，靠 `ENABLE_MOCK_PAYMENTS` 把门。支付适配器已按 `create_intent → confirm → refund` 的真实形态抽象，接真实网关是新增一个类，不是重构调用方。
- **库存只在 PostgreSQL 上严格防超卖**：并发测试依赖行级锁，SQLite 上会被跳过（`1 skipped`）。
- **后台不支持编辑已有商品的文案**：目前只能改状态、变体价格、库存与设置；翻译的整体编辑接口后端已具备，前端未做。
