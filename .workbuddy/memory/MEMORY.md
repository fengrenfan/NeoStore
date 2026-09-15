# 独立站项目 — 长期约定

## 项目定位

轻量**单店** DTC 跨境独立站（代号 NeoStore）。单租户、单店，不做多商户 / marketplace / POS。
多语言与多币种是第一期就要建好的一等公民。

## 技术栈（已定）

- 后端：FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic
- 数据库：PostgreSQL 16
- 缓存/队列：Redis 7 + arq
- 顾客端：Next.js（App Router, TS）—— 必须 SSR，SEO 是独立站命脉
- 管理后台：Vite + React + TanStack Query/Table
- 样式：Tailwind，深色底 + 霓虹/渐变高亮
- 部署：Docker Compose + Caddy

## 架构硬约束（改代码前先看这条）

1. `backend/app/domain/` **禁止** import fastapi，禁止直接持有 Session；持久化经 repository 接口。
2. 金额一律 `Decimal`，禁止 `float`；所有金额计算收敛到 `pricing.calculate()` 单一入口，
   API 层和前端都不做金额运算。
3. **订单行必须快照**商品名 / SKU / 单价到 `order_line`，不许外键回查商品表。
4. 订单状态只能通过 `order.mark_*()` 显式方法流转，每次流转写 `order_event` 审计。
5. 多语言用独立翻译表 `*_translation`，`UNIQUE(entity_id, locale)`；回退链
   「请求 locale → 默认 locale → 空」在服务层统一处理，不透传前端。
6. 多币种：显式定价优先，缺失时按最新汇率换算兜底，结果按目标币种 decimal_places 取整。
7. 前端 TS 类型从 OpenAPI 生成（`openapi-typescript`），禁止手写 interface。

## 协作约定

- 交付物要给能直接看 / 能直接跑的形态。
- 大改动（架构、删数据、上线）过确认；小改动直接做。
