# NeoStore — 轻量单店 DTC 跨境独立站 设计文档

- 日期：2026-09-15
- 状态：待评审
- 代号：NeoStore（名称可改，仅作目录与命名空间占位）

## 1. 背景与目标

调研 GitHub 头部开源电商项目（Medusa / Bagisto / Saleor / Spree / Vendure）后确认：
五个项目的语言与框架各不相同，但领域模型链路、分层方式、扩展机制高度一致。本项目复用其
被验证过的架构范式，但把范围收窄到「单店 DTC 独立站」，剔除多租户、多商户、POS、
marketplace 等本期不需要的复杂度。

**目标**

1. 跑通一条完整可用的跨境购物闭环：浏览 → 加购 → 结算 → 下单 → 后台处理。
2. 多语言与多币种作为**一等公民**在第一期建好，避免后期改表。
3. 领域层与 Web 框架解耦，可独立测试、可替换。
4. 全部可自托管，一个 `docker compose up` 起全栈。

**非目标（本期明确不做）**

- 多商户 / 卖家入驻 / 分账
- 多租户（单店，单租户）
- 真实支付网关对接（第一期用模拟支付适配器，接口留好）
- 会员账号体系（注册登录、地址簿、订单历史）
- Elasticsearch 全文检索（第一期用 PostgreSQL `pg_trgm`）
- 移动端 App、小程序

## 2. 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 后端框架 | FastAPI + Pydantic v2 | 类型驱动、自动 OpenAPI、异步 |
| ORM / 迁移 | SQLAlchemy 2.0 + Alembic | 2.0 风格显式类型标注，迁移可靠 |
| 数据库 | PostgreSQL 16 | JSONB、GIN 索引、`pg_trgm`、事务与并发控制成熟，电商领域标准 |
| 缓存 / 队列 | Redis 7 + arq | 购物车会话、汇率缓存、定时任务 |
| 顾客端 | Next.js（App Router, TS） | 独立站依赖自然流量，必须 SSR/ISR；SEO 能力是硬需求 |
| 管理后台 | Vite + React + TanStack | 后台是表格表单密集的重应用，SPA 更顺手，重依赖不污染顾客端 |
| 样式 | Tailwind CSS | 深色底 + 霓虹/渐变高亮主题 |
| 部署 | Docker Compose + Caddy | Caddy 负责反代与自动 HTTPS |

## 3. 目录结构

```
独立站/
├── backend/                      # FastAPI 服务
│   ├── app/
│   │   ├── main.py               # 应用装配、中间件、异常处理器
│   │   ├── core/                 # config.py security.py errors.py deps.py
│   │   ├── db/                   # base.py session.py
│   │   ├── domain/               # 纯业务逻辑，不 import fastapi
│   │   │   ├── i18n/             # locale、翻译表基类、回退策略
│   │   │   ├── currency/         # 币种、汇率、换算服务
│   │   │   ├── region/           # 区域：币种 + 语言 + 税 + 支付方式
│   │   │   ├── catalog/          # 商品 / 变体 / SKU / 分类 / 选项 / 媒体
│   │   │   ├── pricing/          # 定价策略：显式价优先，汇率兜底
│   │   │   ├── inventory/        # 库存与预占
│   │   │   ├── cart/             # 购物车
│   │   │   ├── order/            # 订单与状态机
│   │   │   └── payment/          # 支付适配器接口
│   │   ├── api/v1/
│   │   │   ├── store/            # 顾客端接口
│   │   │   ├── admin/            # 后台接口
│   │   │   └── router.py
│   │   └── integrations/         # 汇率源、邮件、支付网关适配器实现
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   └── Dockerfile
├── storefront/                   # Next.js 顾客端
├── admin/                        # Vite + React 后台
├── docker-compose.yml
├── Caddyfile
└── docs/
```

**分层依赖方向（单向，不可逆）**

```
api  →  domain  →  db
 ↓        ↓
integrations（仅被 domain 通过接口调用）
```

`domain/` 内部禁止出现 `fastapi`、`httpx`、`sqlalchemy.orm.Session` 的直接依赖；
持久化通过 repository 接口注入，便于单测与替换。

## 4. 领域模型

### 4.1 多语言（i18n）

采用「独立翻译表」而非 JSONB 内嵌字段。理由：可加唯一约束与复合索引、可直接被
`pg_trgm` 检索、locale 可动态增删、缺翻译时回落逻辑清晰。

- `locale(code PK, name, is_active, is_default, position)`
- `product_translation(product_id, locale, name, slug, description, seo_title, seo_description)`
  - `UNIQUE(product_id, locale)`，`UNIQUE(locale, slug)`
- `category_translation`、`option_value_translation`：同构

**回退链**：请求 locale → 默认 locale → 空值。回退在服务层统一处理，不透传给前端。

### 4.2 多币种

- `currency(code PK, symbol, decimal_places, is_active)`
- `exchange_rate(base_code, quote_code, rate, source, fetched_at)`
  - `UNIQUE(base_code, quote_code)`，每次拉取后更新
- `variant_price(variant_id, currency_code, amount)`
  - `UNIQUE(variant_id, currency_code)`，可为 NULL 表示未显式定价

**定价策略（关键）**：显式定价存在时直接使用；不存在时 `base_price × 最新汇率` 兜底。
这解决「小众币种不必逐个定价」的问题，与 Medusa Region 的思路一致。换算结果按目标币种
`decimal_places` 取整，避免出现 `$19.9999`。

### 4.3 区域 Region

- `region(code, name, currency_code, tax_rate, is_default, position)`
- `region_locale(region_id, locale)` — 一个区域可用哪些语言
- `region_payment_method(region_id, provider_code, is_active)`

区域是「币种 + 语言集合 + 税率 + 可用支付方式」的聚合。前台按访客区域决定展示内容。
单店场景下区域数量通常在 2–5 个，不做复杂规则引擎。

### 4.4 Catalog

- `product(id, status, product_type, created_at, updated_at)`
  - `status`: `draft | published | archived`
- `product_variant(id, product_id, sku UNIQUE, position)` — **SKU 是最小可售单元**
- `product_option(id, product_id, name)`、`option_value(id, option_id, position)`
- `variant_option_value(variant_id, option_value_id)` — 变体与选项值的多对多
- `category(id, parent_id, path, position)` — `path` 物化路径，便于整棵子树查询
- `product_category(product_id, category_id)`
- `media(id, owner_type, owner_id, url, alt, position)` — 通用附件表
- `inventory_item(variant_id, quantity, reserved)` + `stock_movement(变体, 变化量, 原因, 时间)`

### 4.5 Cart 与 Order

- `cart(id, token UNIQUE, region_code, currency_code, status, expires_at)`
  - `status`: `active | converted | abandoned`
  - 匿名购物车用不可猜测的 `token` 标识，签发短期 JWT 放 Cookie
- `cart_line(cart_id, variant_id, quantity, unit_price, currency_code)`
  - `unit_price` 是加入时快照，避免会话中途变价导致金额跳变
- `order(id, number UNIQUE, status, region_code, currency_code, email, shipping_address JSONB,
  subtotal, shipping_fee, tax, total, idempotency_key UNIQUE, created_at)`
- `order_line(order_id, variant_id, product_name, variant_label, sku, unit_price, quantity,
  line_total, currency_code)`

**订单必须快照**：`order_line` 冗余存商品名、SKU、单价，不通过外键回查商品表。
否则后台改商品名或改价会污染历史订单。五个参考项目全部这么做，这是硬约束。

**订单状态机**

```
draft → awaiting_payment → paid → fulfilled → completed
   ↓            ↓             ↓        ↓
cancelled   cancelled     refunded  refunded
```

状态流转只允许在服务层通过显式方法触发（`order.mark_paid()`），禁止直接改字段，
每次流转写一条 `order_event` 审计记录。

### 4.6 库存与超卖防护

下单时在事务内 `SELECT ... FOR UPDATE` 锁行，校验 `quantity - reserved >= 请求量`，
通过后增加 `reserved`；支付成功后 `reserved` 转为实扣并写 `stock_movement`。
取消或超时未支付则释放预占。首期不做分布式锁。

### 4.7 定价计算（单一入口）

`pricing.calculate(cart, region, locale) -> PriceBreakdown`，返回
`subtotal / shipping_fee / tax / total / currency`。所有金额计算收敛到这一处，
禁止在 API 层或前端做金额运算。金额统一用 `Decimal`，禁止用 `float`。

## 5. API 设计

- 统一前缀 `/api/v1`
- 顾客端：`/api/v1/store/*`
  - `GET /locales`、`GET /regions`
  - `GET /products`（分页、分类筛选、排序）、`GET /products/{slug}`
  - `POST /carts`、`GET /carts/{token}`、`PATCH /carts/{token}/lines`、`DELETE /carts/{token}/lines/{id}`
  - `POST /checkout`、`GET /orders/{number}`
- 后台：`/api/v1/admin/*`
  - 商品 / 变体 / 分类 / 媒体 CRUD（含多语言字段）
  - `GET /orders`、`GET /orders/{id}`、`PATCH /orders/{id}/status`
  - `GET|PATCH /regions`、`GET /currencies`、`POST /exchange-rates/refresh`
  - 库存调整 `POST /inventory/{variant_id}/adjust`

**横切约定**

- 语言协商：`Accept-Language`，可被 `?locale=` 显式覆盖；响应回 `Content-Language`
- 区域协商：`X-Region` 或 `?region=`；响应回 `X-Currency`
- 幂等：`POST /checkout` 支持 `Idempotency-Key` 头，同 key 重复请求返回同一订单
- 统一错误体：`{"error": {"code": "...", "message": "...", "details": {...}}}`
- 分页：`limit` / `offset`，总数放 `X-Total-Count`
- 鉴权：顾客端用购物车 token；后台用 JWT（access + refresh），角色字段留好
- 类型同步：前端 TS 类型从 OpenAPI 生成（`openapi-typescript`），禁止手写 interface

## 6. 前端

### 6.1 storefront（Next.js App Router）

- 路由：`/[locale]/products`、`/[locale]/products/[slug]`、`/[locale]/cart`、`/[locale]/checkout`
- `middleware.ts` 负责 locale / region 检测与重定向（路径前缀 → cookie → Accept-Language）
- 读取：Server Component 内直连 FastAPI；写入：Route Handler 代理以保护 token
- 缓存：`revalidate` + 接口 ETag；商品页 ISR
- SEO：`generateMetadata` 输出 title/description/OG/hreflang，`sitemap.ts`、`robots.ts`、
  JSON-LD `Product` + `Offer` 结构化数据
- 客户端状态：购物车用轻量 store，不引重型状态库
- 视觉：深色底 + 霓虹/渐变高亮

### 6.2 admin（Vite + React）

- TanStack Query + TanStack Table + react-hook-form + zod
- 页面：商品 CRUD（多语言以 Tab 切 locale 编辑）、分类、媒体、库存、订单列表与详情、
  区域与币种配置、语言开关
- 权限位预留在路由层，本期不做完整 RBAC

## 7. 基础设施与部署

- `docker-compose.yml` 服务：`db`(PG16) / `redis`(7) / `api` / `storefront` / `admin` / `caddy`
- 健康检查：`/healthz`（存活）、`/readyz`（含 DB 与 Redis 连通性）
- 迁移：`alembic upgrade head` 作为 api 容器启动前置步骤
- 种子数据：一个 `seed` 命令，灌入 2 个 locale（zh-CN/en）、2 个 currency（CNY/USD）、
  2 个 region、若干商品，保证起库后即可浏览
- 配置：`pydantic-settings` 读 `.env`，密钥不入库不入 Git，提供 `.env.example`
- 日志：结构化 JSON，请求带 `request_id`

## 8. 错误处理

- `DomainError` 基类 + 子类（`NotFound`、`ValidationFailed`、`InsufficientStock`、
  `CartExpired`、`PaymentFailed`），全局 handler 映射为 4xx 并附业务错误码
- 未捕获异常统一 500，只记日志不外泄堆栈
- Pydantic schema 分层：`XxxCreate` / `XxxUpdate` / `XxxRead`，不共用

## 9. 测试策略

- 后端：pytest + httpx `AsyncClient`，每个用例跑在事务里并回滚
- 重点覆盖（这几处最容易出错）：
  1. 定价换算与取整（含汇率缺失、显式价覆盖）
  2. 库存并发扣减不超卖（并发请求断言最终库存）
  3. i18n 回退链（缺 en 翻译时回落 zh-CN）
  4. 下单幂等（同 `Idempotency-Key` 返回同一订单）
  5. 订单快照不被商品改动污染
- 前端：Playwright 跑一条「切换语言 → 切换币种 → 加购 → 下单」的端到端冒烟

## 10. 里程碑

| 阶段 | 内容 | 验收标准 |
|---|---|---|
| M0 | 脚手架与基础设施 | `docker compose up` 起全栈，`/healthz` 通过，Alembic 空迁移可跑 |
| M1 | i18n + 多币种核心 | locale/currency/region/汇率表与换算服务就绪，单测覆盖回退与换算 |
| M2 | Catalog | 商品/变体/SKU/分类/媒体落库，前后台可读 |
| M3 | Cart & Checkout | 匿名购物车 → 结算 → 模拟支付 → 生成订单快照 |
| M4 | 后台管理 | 商品多语言编辑、订单状态流转、库存调整 |
| M5 | 打磨 | SEO/hreflang/sitemap、幂等、并发防护、端到端冒烟 |

**首期交付 = M0–M4**，M5 视情况推进。

## 11. 已确认的决策记录

| 决策 | 结论 | 依据 |
|---|---|---|
| 项目形态 | 轻量单店 DTC 独立站 | 用户确认 |
| 技术栈 | FastAPI + React | 用户确认 |
| 前端工程结构 | Next.js 店面 + 独立 Vite 后台 | SEO 与模块边界 |
| 数据库 | PostgreSQL | JSONB/索引/并发能力，电商领域标准 |
| 首期范围 | 最小可用闭环 | 用户确认 |

## 12. 补充决策（已确认）

| 项 | 结论 |
|---|---|
| 项目名称 | **NeoStore**（正式使用，不再是占位代号） |
| 汇率数据源 | 对接**开放汇率 API**（适配器模式，可替换源；拉取失败时用库中最后一条汇率并记录告警） |
| 支付网关 | 首期**仅模拟适配器**，但接口按真实网关的形态设计（创建支付意图 → 回跳/回调 → 幂等确认），后期接入无需改调用方 |
| 视觉主色 | **深色底 + 霓虹渐变高亮**；主强调色 `#7C5CFF`（紫）→ `#22D3EE`（青）渐变，涨/正向态用 `#34D399` |

### 汇率 API 设计补充

- 适配器接口：`ExchangeRateProvider.fetch(base) -> dict[str, Decimal]`
- 默认实现 `OpenExchangeRateProvider`，走可配置的 `EXCHANGE_RATE_API_URL` 与 `EXCHANGE_RATE_API_KEY`
- 定时任务（arq cron）每 6 小时刷新；刷新失败不覆盖已有值，仅写日志
- 后台提供 `POST /api/v1/admin/exchange-rates/refresh` 手动触发，以及手工覆盖单条汇率的接口

### 支付适配器设计补充

- 接口：`PaymentProvider.create_intent(order) -> PaymentIntent`、
  `confirm(intent_id) -> PaymentResult`、`refund(payment_id, amount) -> RefundResult`
- 首期实现 `MockPaymentProvider`：`create_intent` 直接返回可立即确认的意图
- `payment` 表存 `provider` / `provider_ref` / `status`，真实网关接入时只替换实现类
