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

> 上图是 compose 内部的视角。线上在 Caddy 之前还有一层宿主 nginx 负责 TLS，见「线上部署」。

## 现状

- M0–M4 全部落地：后端领域层与两套 API、顾客端、后台、编排与部署。
- 后端测试 **150 passed / 1 skipped**（跳过的是依赖 PostgreSQL 行级锁的防超卖并发用例，SQLite 上跑不了）；`ruff` 全绿。
- 已上线 <https://store.xiaodigua.shop>，并被服务器看门狗巡检。
- 还没接真实支付网关（见「已知取舍」）；种子数据的商品图指向占位 CDN，前端会自动降级成品牌渐变块。

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
| `scripts/storefront-check.cjs` | 顾客端的**真实浏览器**检查（15 项断言） |
| `scripts/admin-check.cjs` | 后台的真实浏览器检查 |
| `scripts/nginx/` | 线上 nginx 站点配置模板（换机器时重放用） |
| `docs/RUNBOOK.md` | 运维手册：访问入口、发布与迁移、备份恢复、换汇率源、接真实支付、上线检查清单 |
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

## 线上部署

线上是**单机 Docker Compose**，代码在 `124.222.204.236:/home/app/store`，对外只有一个域名：

| 入口 | 地址 |
|---|---|
| 顾客端 | <https://store.xiaodigua.shop> |
| 管理后台 | <https://store.xiaodigua.shop/admin/> |
| API | `https://store.xiaodigua.shop/api/v1/...` |
| 健康检查 | `/healthz`、`/readyz`（挂在 Caddy 根路径，**不带** `/api` 前缀） |

链路：宿主 nginx（80/443 + certbot 证书）→ `127.0.0.1:8091` Caddy → 按前缀分流到
api / admin / storefront。**Caddy 是唯一入口，不要绕过它直连容器端口。**

服务器专属、**不入库**的两份配置（每台机器各不相同，只写一次）：`backend/.env` 与
`docker-compose.override.yml` —— 里面是发布端口、包镜像源、生成的 `JWT_SECRET` / 管理员密码、
`NEXT_PUBLIC_SITE_URL`。

```bash
cd /home/app/store
COMPOSE_PARALLEL_LIMIT=1 docker compose build <service>   # 串行构建，这台机器内存紧
docker compose up -d --force-recreate <service>           # 注意：镜像变新时 up -d 不会自动重建容器
docker compose ps
curl -fsS localhost:8091/readyz
```

生产镜像的 `NEXT_PUBLIC_API_BASE_URL` **故意留空**，于是浏览器请求同源的 `/api/v1/...`：
同一份镜像放在端口、子域名或 HTTPS 后面都不用重新构建；server component 仍走容器内的
`API_BASE_URL=http://api:8000`。`NEXT_PUBLIC_*` 与 `NEXT_PUBLIC_SITE_URL` 都是**构建期内联**的，
改了要重新 build，光重启不生效。

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
| `node scripts/storefront-check.cjs <地址>` | 真实浏览器走买家链路：落地 → 浏览 → 加购 → 购物车 → 结算 → 切语言，15 项断言，含「所有 API 请求停留在本源」；零 console 报错 |
| `node scripts/admin-check.cjs <后台地址> <订单号>` | 用真实浏览器把后台走一遍（登录 → 概览 → 各页 → 状态流转），失败即非零退出 |
| `node scripts/currency-repro.cjs <地址>` | 切区域下拉，报告价格币种是否真的变了 + 浏览器实际发出的商品请求 URL（排查「切货币不生效」用） |
| `cd backend && .venv/bin/python -m pytest` | 后端测试 |
| `cd backend && .venv/bin/ruff check .` | 后端 lint（含"domain 层禁止 import fastapi"规则） |
| `cd storefront && npm run build` | 顾客端构建 |
| `cd admin && npm run typecheck && npm run build` | 后台类型检查与构建 |
| `alembic revision --autogenerate -m "..."` | 生成迁移（在 `backend/` 下执行） |

冒烟脚本会自己挑 8010/3110/3111 三个端口；被占用时直接报错退出，不会误连别人的服务。端口可用环境变量换：`API_PORT=9010 WEB_PORT=9110 ADMIN_PORT=9111 bash scripts/smoke.sh`。

> `storefront-check.cjs` 的第二个参数会改变它访问的 locale，但**断言文案写死中文**，
> 所以别传非 `zh-CN` 的值（会整片假报失败）。两个浏览器脚本都需要 Playwright + Chromium。

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

### 顾客端：区域（币种）与语言怎么解析

**区域由 URL 的 `?region=` 承载**，它是唯一可信来源；middleware 把它注入 `x-neostore-region`
请求头，server component 优先读这个头。这段链路踩过三个坑，改之前先看：

- **`searchParams` 在 standalone 构建的运行时是 `undefined`**，即使声明了 `force-dynamic`。
  页面一律用 `lib/server.ts` 的 `regionFromSearchParams(await searchParams)`，不要直接解引用
  （直接读 `sp.region` 会 `TypeError` → 500）。
- **cookie 名等共享常量放 `lib/constants.ts`**（不带 `"use client"`）。从 `"use client"` 模块
  导入的**值**在服务端运行时会变成 `undefined`，而 `request.cookies.get(undefined)` 永远不匹配、
  失败得悄无声息。（`request.cookies.get()` 本身是好的，别怀疑它。）
- **cookie → URL 的续接必须用 307 重定向**，不能用 `rewrite`：同路径的 rewrite 会被静态预渲染
  吞掉，货币静默退回默认。目标 URL 要用 `new URL(request.url)` 构造，`nextUrl.clone()` 会丢 query
  导致重定向死循环。

语言解析顺序是「路径前缀 → 记住的 cookie → `Accept-Language` → 默认」。

## 运维

运维脚本都在**服务器**上，不进仓库（改之前先备份）：

| 任务 | 位置 | 调度 |
|---|---|---|
| 容器看门狗 | `/home/ubuntu/server-watchdog.sh` | crontab，每 2 分钟 |
| 每周磁盘清理 | `/home/ubuntu/server-disk-cleanup.sh` | crontab，每周日 04:10 |
| MySQL 备份 | `/home/ubuntu/backup-mysql.sh` | crontab，每天 03:00 |

**看门狗**巡检 16 个容器（cosmetics 4 / blog 5 / **neostore 7**）：容器 `missing` 就走
`docker compose up -d`、非 running 走 `docker start`、`unhealthy` 走 `docker restart`。
只要有动作就发告警邮件（同一容器 30 分钟冷却，连续 3 次拉不起来升级为「严重」），
每天 09 点发一封心跳汇总。日志：`/home/ubuntu/server-watchdog.log`。

**磁盘清理**只做可重建的清理：悬空镜像、构建缓存、停超 7 天的容器、journal 压到 200M。
**刻意不用 `docker image prune -a`** —— 这台机器 Docker Hub 直连不通、镜像源大半失效，
带 tag 的基础镜像（python / node / maven / temurin）是**离线构建的前提**，删了下次构建就要重拉。

> 注意：`quant-engine` / `quant-web` / `quant-backend` 三个容器**不在**看门狗清单里，
> 挂了不会自动恢复。看门狗只看容器状态，**不探 HTTP** —— 容器 healthy 但网站返 500
> 这类故障它发现不了。

## 已知取舍

- **演示闭环优先**：没有真实支付网关，`/store/orders/{number}/pay` 是替代品，靠 `ENABLE_MOCK_PAYMENTS` 把门。支付适配器已按 `create_intent → confirm → refund` 的真实形态抽象，接真实网关是新增一个类，不是重构调用方。
- **库存只在 PostgreSQL 上严格防超卖**：并发测试依赖行级锁，SQLite 上会被跳过（`1 skipped`）。
- **后台不支持编辑已有商品的文案**：目前只能改状态、变体价格、库存与设置；翻译的整体编辑接口后端已具备，前端未做。
