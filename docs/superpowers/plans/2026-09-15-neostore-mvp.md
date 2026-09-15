# NeoStore MVP 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一个可 `docker compose up` 起全栈的跨境单店独立站：多语言、多币种、商品浏览、匿名购物车、结算下单、后台管理全链路跑通。

**Architecture:** FastAPI 单体分层（api → domain → db，domain 不依赖 Web 框架）；PostgreSQL 持久化，Redis 承担购物车会话与汇率定时任务；Next.js 负责 SEO 敏感的顾客端，独立 Vite React 应用负责后台。

**Tech Stack:** Python 3.13 / FastAPI / Pydantic v2 / SQLAlchemy 2.0 / Alembic / PostgreSQL 16 / Redis 7 / arq / Next.js 15 (App Router) / Vite + React 19 / TanStack Query + Table / Tailwind CSS / Docker Compose / Caddy

## Global Constraints

- Python 版本下限 `>=3.13`；包管理用 `uv`（fallback：`pip` + `venv`）。
- 金额类型**必须**是 `decimal.Decimal`，禁止 `float`。DB 列用 `NUMERIC(14, 4)`。
- `backend/app/domain/**` 内**禁止** import `fastapi`、`starlette`；禁止直接持有 `Session`，持久化一律经 repository 接口。
- 多语言翻译表命名固定 `<entity>_translation`，唯一约束固定 `UNIQUE(<entity>_id, locale)`。
- 回退链固定：请求 locale → `locale.is_default = true` 的 locale → 空值。
- 订单行**必须**快照 `product_name` / `variant_label` / `sku` / `unit_price` / `currency_code`，禁止外键回查商品表。
- 订单状态只能经 `Order.mark_*(...)` 方法流转，每次流转写一条 `order_event`。
- 汇率多币种定价策略固定：`variant_price` 有显式记录则用之；否则 `base_price * rate`，结果按下单币种 `decimal_places` 用 `ROUND_HALF_UP` 取整。
- 所有 API 前缀 `/api/v1`；错误体固定 `{"error": {"code", "message", "details"}}`。
- 视觉主色：底 `#0B0B12`，强调渐变 `#7C5CFF → #22D3EE`，正向态 `#34D399`。前端不得引入其他主色。
- 每个 Task 结束必须 commit，commit 信息用 `feat:` / `test:` / `chore:` 前缀。

---

## 文件结构总览

```
独立站/
├── backend/
│   ├── app/
│   │   ├── main.py                       # 应用装配、中间件、异常处理器
│   │   ├── seed.py                       # 种子数据命令
│   │   ├── core/{config,errors,security,deps,logging}.py
│   │   ├── db/{base,session}.py
│   │   ├── domain/
│   │   │   ├── i18n/{models,repository,service,schemas}.py
│   │   │   ├── currency/{models,repository,service,schemas}.py
│   │   │   ├── region/{models,repository,service,schemas}.py
│   │   │   ├── catalog/{models,repository,service,schemas}.py
│   │   │   ├── pricing/service.py
│   │   │   ├── inventory/{models,repository,service}.py
│   │   │   ├── cart/{models,repository,service,schemas}.py
│   │   │   ├── order/{models,repository,service,state_machine,schemas}.py
│   │   │   └── payment/{base,mock,service}.py
│   │   ├── integrations/{exchange_rate,mailer}.py
│   │   └── api/v1/
│   │       ├── router.py
│   │       ├── store/{locales,regions,products,carts,checkout,orders}.py
│   │       └── admin/{auth,products,categories,orders,inventory,settings}.py
│   ├── alembic/{env.py,versions/}
│   ├── tests/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── .env.example
├── storefront/                           # Next.js
├── admin/                                # Vite + React
├── docker-compose.yml
├── Caddyfile
├── README.md
└── docs/superpowers/{specs,plans}/
```

---

## Task 1: 可运行的空服务 + 容器编排

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/main.py`, `backend/app/core/config.py`, `backend/app/api/v1/router.py`, `backend/Dockerfile`, `backend/.env.example`, `docker-compose.yml`, `Caddyfile`, `.gitignore`, `README.md`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `app.core.config.Settings`（`pydantic-settings`，字段 `database_url: str`、`redis_url: str`、`jwt_secret: str`、`exchange_rate_api_url: str`、`exchange_rate_api_key: str`、`default_locale: str = "zh-CN"`）；`app.core.config.get_settings()`（`lru_cache`）；`app.main.create_app() -> FastAPI`；健康检查端点 `GET /healthz` → `{"status":"ok"}`、`GET /readyz` → `{"status":"ok","db":true,"redis":true}`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_health.py`
```python
from httpx import ASGITransport, AsyncClient
import pytest
from app.main import create_app

@pytest.mark.anyio
async def test_healthz():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: 写实现**

`backend/pyproject.toml`（要点：`requires-python = ">=3.13"`；deps: `fastapi`、`uvicorn[standard]`、`pydantic-settings`、`sqlalchemy>=2.0`、`alembic`、`asyncpg`、`redis`、`arq`、`python-jose[cryptography]`、`httpx`；dev-deps: `pytest`、`pytest-anyio`、`anyio`、`ruff`）

`backend/app/core/config.py`
```python
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+asyncpg://neostore:neostore@db:5432/neostore"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = "change-me"
    exchange_rate_api_url: str = "https://open.er-api.com/v6/latest"
    exchange_rate_api_key: str = ""
    default_locale: str = "zh-CN"
    default_currency: str = "USD"

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
```

`backend/app/main.py`
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.api.v1.router import api_router
from app.db.session import dispose_engine, ping_db
from app.core.errors import register_exception_handlers

def create_app() -> FastAPI:
    app = FastAPI(title="NeoStore API", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz", tags=["ops"])
    async def readyz() -> dict:
        return {"status": "ok", "db": await ping_db(), "redis": True}

    return app

app = create_app()
```

`backend/app/api/v1/router.py`
```python
from fastapi import APIRouter
api_router = APIRouter()
```

`backend/Dockerfile`
```dockerfile
FROM python:3.13-slim
WORKDIR /srv
RUN pip install --no-cache-dir uv
COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml || uv pip install --system .
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

`docker-compose.yml`：服务 `db`(postgres:16-alpine, healthcheck `pg_isready`)、`redis`(redis:7-alpine)、`api`(build `./backend`, `depends_on: db/redis healthy`, 挂 `.env`, 启动前跑 `alembic upgrade head`)、`storefront`、`admin`、`caddy`（卷：`Caddyfile`, `caddy_data`）。命名卷 `pgdata`。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: 起容器验证**

Run: `docker compose up -d db redis api && sleep 5 && curl -s localhost:8000/healthz`
Expected: `{"status":"ok"}`

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "chore: scaffold fastapi service with docker compose and health checks"
```

---

## Task 2: 数据库基座与 Alembic

**Files:**
- Create: `backend/app/db/base.py`, `backend/app/db/session.py`, `backend/alembic.ini`, `backend/alembic/env.py`, `backend/alembic/script.py.mako`
- Test: `backend/tests/conftest.py`, `backend/tests/test_db.py`

**Interfaces:**
- Consumes: `app.core.config.settings`
- Produces: `app.db.base.Base`（`DeclarativeBase`，含 `metadata` 命名约定）；`app.db.session.engine`、`async_session_factory`、`get_session()`（FastAPI 依赖，`AsyncGenerator[AsyncSession, None]`）、`ping_db() -> bool`、`dispose_engine()`；`Numeric(14, 4)` 金额列助手 `app.db.base.Money`。

`metadata` 命名约定（必须，否则 Alembic 自动生成的约束名不稳定）：
```python
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
```

- [ ] **Step 1: 写失败测试**

`backend/tests/conftest.py`——提供 `anyio_backend` fixture 返回 `"asyncio"`；提供 `db_session` fixture：连一个**测试库**（`settings.database_url` 加 `_test` 后缀，或用环境变量 `TEST_DATABASE_URL`），每个用例包在事务里、结束回滚；提供 `client` fixture（`AsyncClient` + `ASGITransport`，依赖覆盖 `get_session` → `db_session`）。

`backend/tests/test_db.py`
```python
import pytest
from app.db.session import ping_db

@pytest.mark.anyio
async def test_ping_db():
    assert await ping_db() is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && uv run pytest tests/test_db.py -v`
Expected: FAIL — `ImportError` 或连接失败

- [ ] **Step 3: 写实现**

`app/db/base.py`：`Base` + `NAMING_CONVENTION` + `Money = Numeric(14, 4)`；提供 `TimestampMixin`（`created_at`、`updated_at`，`server_default=func.now()`，`onupdate=func.now()`）。

`app/db/session.py`：
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from app.core.config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        yield session

async def ping_db() -> bool:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False

async def dispose_engine() -> None:
    await engine.dispose()
```

`alembic/env.py`：`target_metadata = Base.metadata`；**必须** import 所有 domain models 模块以保证 autogenerate 能发现表（在 env.py 顶部集中 import，或让 `app/domain/__init__.py` 汇总导出）。

- [ ] **Step 4: 跑测试确认通过**

Run: `cd backend && uv run pytest tests/test_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: add sqlalchemy base, async session and alembic wiring"
```

---

## Task 3: 统一错误处理

**Files:**
- Create: `backend/app/core/errors.py`
- Test: `backend/tests/test_errors.py`

**Interfaces:**
- Produces: `DomainError(code: str, message: str, status_code: int = 400, details: dict | None = None)`；子类 `NotFoundError`(404)、`ValidationFailedError`(422)、`InsufficientStockError`(409)、`CartExpiredError`(410)、`PaymentFailedError`(402)、`IdempotencyConflictError`(409)；`register_exception_handlers(app)`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_domain_error_shape(client):
    from app.main import create_app
    app = create_app()
    @app.get("/boom")
    async def boom():
        raise NotFoundError(code="PRODUCT_NOT_FOUND", message="not found")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        r = await c.get("/boom")
    assert r.status_code == 404
    assert r.json() == {"error": {"code": "PRODUCT_NOT_FOUND", "message": "not found", "details": {}}}
```

- [ ] **Step 2: 跑测试确认失败** — Run: `uv run pytest tests/test_errors.py -v`；Expected: FAIL

- [ ] **Step 3: 写实现** — `DomainError` + 子类 + `register_exception_handlers`：注册 `DomainError` 处理器返回 `JSONResponse(status_code=e.status_code, content={"error": {...}})`；注册 `RequestValidationError` 处理器转成同形状（`code="VALIDATION_FAILED"`，`details` 放 `exc.errors()` 的简化版）；注册兜底 `Exception` 处理器：记 `logger.exception` 并返回 500 `{"error": {"code": "INTERNAL_ERROR", "message": "internal error", "details": {}}}`，**不得**回传堆栈。

- [ ] **Step 4: 跑测试确认通过** — Expected: PASS

- [ ] **Step 5: Commit** — `git commit -m "feat: add domain error hierarchy with unified response shape"`

---

## Task 4: i18n 领域

**Files:**
- Create: `backend/app/domain/i18n/{models,repository,service,schemas}.py`
- Test: `backend/tests/test_i18n.py`

**Interfaces:**
- Consumes: `Base`, `Money`, `get_session`
- Produces:
  - `Locale` 模型：`code`(PK, str(16))、`name`、`is_active`(bool)、`is_default`(bool)、`position`(int)
  - `TranslationMixin`：提供 `locale`(str(16), PK 组成)、`_owner_table` 约定
  - `I18nService(session)`，方法：
    - `resolve_locale(requested: str | None) -> str` — 回退到默认 locale
    - `translate(rows: Sequence[TranslationMixin], locale: str, default_locale: str) -> TranslationMixin | None` — 通用单条回退
    - `list_active_locales() -> list[Locale]`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_resolve_locale_falls_back(db_session):
    from app.domain.i18n.service import I18nService
    svc = I18nService(db_session)
    assert await svc.resolve_locale("en") == "en"          # 已存在且 active
    assert await svc.resolve_locale("ja") == "zh-CN"       # 不存在 → 默认
    assert await svc.resolve_locale(None) == "zh-CN"

@pytest.mark.anyio
async def test_translate_prefers_requested_then_default(db_session):
    # fixture 已插入 product 的 zh-CN 与 en 两行翻译
    row = await svc.translate(rows, locale="fr")   # fr 无翻译
    assert row.locale == "zh-CN"
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL

- [ ] **Step 3: 写实现** — `Locale` 建表（`__tablename__ = "locale"`）；`TranslationMixin` 用 `@declared_attr` 声明 `locale` 列与 `__table_args__` 的 `UniqueConstraint`；`I18nService.translate` 实现「精确匹配 → 默认 locale → None」三段回退。

- [ ] **Step 4: 跑测试确认通过** — Expected: PASS

- [ ] **Step 5: Commit** — `git commit -m "feat: add i18n locale registry with translation fallback chain"`

---

## Task 5: 多币种与汇率

**Files:**
- Create: `backend/app/domain/currency/{models,repository,service,schemas}.py`、`backend/app/integrations/exchange_rate.py`
- Test: `backend/tests/test_currency.py`

**Interfaces:**
- Produces:
  - `Currency`：`code`(PK, str(3))、`symbol`、`decimal_places`(int, 默认 2)、`is_active`
  - `ExchangeRate`：`base_code`、`quote_code`（联合 PK）、`rate`(Numeric(20, 10))、`source`、`fetched_at`
  - `ExchangeRateProvider`（ABC）：`async fetch(base: str) -> dict[str, Decimal]`
  - `OpenExchangeRateProvider(base_url, api_key)`：GET `{base_url}/{base}`，解析 `rates`；非 200 或缺少 `rates` 抛 `ExchangeRateUnavailableError`
  - `StaticRateProvider(rates)`：测试用
  - `CurrencyService(session, provider)`：`convert(amount: Decimal, from_code: str, to_code: str) -> Decimal`、`refresh_rates(base: str) -> int`（返回更新条数）
  - `round_money(amount: Decimal, code: str) -> Decimal` 使用 `ROUND_HALF_UP` 与币种 `decimal_places`

- [ ] **Step 1: 写失败测试**

```python
def test_round_money_half_up():
    assert round_money(Decimal("19.999"), code="USD") == Decimal("20.00")

@pytest.mark.anyio
async def test_convert_uses_stored_rate(db_session):
    svc = CurrencyService(db_session, StaticRateProvider({}))
    got = await svc.convert(Decimal("100.00"), "USD", "CNY")
    assert got == Decimal("725.00")     # 已存 1 USD = 7.25 CNY

@pytest.mark.anyio
async def test_refresh_rates_writes_rows(db_session):
    provider = StaticRateProvider({"CNY": Decimal("7.10"), "EUR": Decimal("0.92")})
    n = await CurrencyService(db_session, provider).refresh_rates("USD")
    assert n >= 2

@pytest.mark.anyio
async def test_refresh_failure_keeps_existing(db_session):
    with pytest.raises(ExchangeRateUnavailableError):
        await CurrencyService(db_session, FailingProvider()).refresh_rates("USD")
    # 断言原汇率仍存在且未被清空
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL

- [ ] **Step 3: 写实现** — 按上述接口实现；`refresh_rates` 用 `INSERT ... ON CONFLICT (base_code, quote_code) DO UPDATE`；异常路径**不得**删除或清空既有行。

- [ ] **Step 4: 跑测试确认通过** — Expected: PASS

- [ ] **Step 5: Commit** — `git commit -m "feat: add currency, exchange rate provider and conversion service"`

---

## Task 6: Region 聚合

**Files:**
- Create: `backend/app/domain/region/{models,repository,service,schemas}.py`
- Test: `backend/tests/test_region.py`

**Interfaces:**
- Consumes: `Currency`, `Locale`
- Produces: `Region`：`code`(PK)、`name`、`currency_code`(FK currency)、`tax_rate`(Numeric(6,4))、`is_default`、`position`；`RegionLocale`：`(region_code, locale)` 联合 PK；`RegionPaymentMethod`：`(region_code, provider_code)` 联合 PK + `is_active`。`RegionService(session)`：`resolve_region(code: str | None) -> Region`（未知 code 回退默认 region）、`list_regions() -> list[Region]`、`available_payment_methods(region_code) -> list[str]`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_resolve_region_falls_back_to_default(db_session):
    svc = RegionService(db_session)
    assert (await svc.resolve_region("XX")).code == "us"
    assert (await svc.resolve_region(None)).code == "us"

@pytest.mark.anyio
async def test_region_carries_currency_and_locales(db_session):
    r = await RegionService(db_session).resolve_region("cn")
    assert r.currency_code == "CNY"
    assert "zh-CN" in await RegionService(db_session).locales_for("cn")
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现**
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add region aggregate binding currency, locales, tax and payments"`

---

## Task 7: Catalog 领域

**Files:**
- Create: `backend/app/domain/catalog/{models,repository,service,schemas}.py`
- Test: `backend/tests/test_catalog.py`

**Interfaces:**
- Produces:
  - `Product`：`id`(UUID)、`status`(Enum `draft|published|archived`)、`product_type`、`base_price`(Money)、`created_at`、`updated_at`
  - `ProductTranslation`：`(product_id, locale)` PK，字段 `name`、`slug`、`description`、`seo_title`、`seo_description`；`UNIQUE(locale, slug)`
  - `ProductVariant`：`id`、`product_id`、`sku`(UNIQUE)、`position`
  - `ProductOption`、`OptionValue`、`VariantOptionValue`（多对多）
  - `Category`：`id`、`parent_id`、`path`(str, 物化路径如 `1/7/`)、`position`；`CategoryTranslation`
  - `Media`：`owner_type`、`owner_id`、`url`、`alt`、`position`
  - `ProductRepository`：`get_by_slug(slug, locale)`、`list_published(locale, limit, offset, category_id=None)`、`count_published(...)`
  - `CatalogService(session)`：`get_product_by_slug(slug, locale) -> ProductDetail`（含翻译、变体、选项、媒体、价格）；`list_products(locale, region, ...) -> tuple[list[ProductCard], int]`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_get_product_by_slug_returns_requested_locale(db_session):
    d = await CatalogService(db_session).get_product_by_slug("neon-tee", "en")
    assert d.name == "Neon Tee"

@pytest.mark.anyio
async def test_get_product_by_slug_falls_back(db_session):
    d = await CatalogService(db_session).get_product_by_slug("neon-tee", "ja")
    assert d.name == "霓虹 T 恤"          # 回退到 zh-CN

@pytest.mark.anyio
async def test_draft_product_not_listed(db_session):
    cards, total = await CatalogService(db_session).list_products(locale="en", region=None)
    assert all(c.status == "published" for c in cards)
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — repository 用 `selectinload` 预加载翻译/变体/媒体避免 N+1；slug 查询按 `(locale, slug)` 命中后取该 product_id，再取全部翻译交由 i18n 回退。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add catalog domain with localized products and variants"`

---

## Task 8: 定价服务（单一入口）

**Files:**
- Create: `backend/app/domain/pricing/service.py`、`backend/app/domain/pricing/schemas.py`
- Test: `backend/tests/test_pricing.py`

**Interfaces:**
- Consumes: `CurrencyService`, `RegionService`, `VariantPrice`
- Produces: `PriceBreakdown`（dataclass：`currency: str`、`subtotal: Decimal`、`shipping_fee: Decimal`、`tax: Decimal`、`total: Decimal`）；`PricingService(session, currency_service)`，方法 `unit_price(variant, currency_code) -> Decimal`、`calculate(lines: Sequence[CartLineInput], region, currency_code) -> PriceBreakdown`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_explicit_variant_price_wins(db_session):
    # variant 有 USD 显式价 19.99，base_price 是 100.00
    p = await PricingService(db_session).unit_price(variant, "USD")
    assert p == Decimal("19.99")

@pytest.mark.anyio
async def test_missing_variant_price_converts_and_rounds(db_session):
    # variant 无 EUR 显式价，USD base 19.99，1 USD = 0.92 EUR
    p = await PricingService(db_session).unit_price(variant, "EUR")
    assert p == Decimal("18.39")      # 19.99 * 0.92 = 18.3908 → HALF_UP 2 位

@pytest.mark.anyio
async def test_calculate_totals_use_decimal(db_session):
    bd = await PricingService(db_session).calculate(lines, region=cn_region, currency_code="CNY")
    assert bd.total == bd.subtotal + bd.shipping_fee + bd.tax
    assert isinstance(bd.total, Decimal)
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — `unit_price` 先查 `variant_price(variant_id, currency_code)`；无则 `currency_service.convert(base_price, base_currency, currency_code)` 后 `round_money`。`calculate` 累加行小计 → 加运费 → 按 `region.tax_rate` 算税 → 求和，每步都 `round_money` 到目标币种精度。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add pricing service as single entry for money math"`

---

## Task 9: 库存与预占

**Files:**
- Create: `backend/app/domain/inventory/{models,repository,service}.py`
- Test: `backend/tests/test_inventory.py`

**Interfaces:**
- Produces: `InventoryItem`：`variant_id`(PK)、`quantity`、`reserved`；`StockMovement`：`id`、`variant_id`、`delta`、`reason`、`created_at`。`InventoryService(session)`：`reserve(variant_id, qty) -> None`（不足抛 `InsufficientStockError`）、`release(variant_id, qty) -> None`、`commit_reservation(variant_id, qty) -> None`、`available(variant_id) -> int`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_reserve_fails_when_insufficient(db_session):
    with pytest.raises(InsufficientStockError):
        await InventoryService(db_session).reserve(v.id, 999)

@pytest.mark.anyio
async def test_concurrent_reserve_does_not_oversell(db_session_factory):
    # 库存 10，20 个并发各请求 1，最终 reserved 必须 <= 10 且成功次数 == 10
    results = await asyncio.gather(*[_reserve_one() for _ in range(20)], return_exceptions=True)
    ok = [r for r in results if r is None]
    assert len(ok) == 10
    assert await InventoryService(s).available(v.id) == 0
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — `reserve` 用 `SELECT ... FOR UPDATE` 锁 `inventory_item` 行；校验 `quantity - reserved >= qty`；通过则 `reserved += qty` 并写 `stock_movement(reason="reserve")`。`commit_reservation` 同时减 `quantity` 与 `reserved`。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add inventory reservation with row lock oversell guard"`

---

## Task 10: Cart

**Files:**
- Create: `backend/app/domain/cart/{models,repository,service,schemas}.py`
- Test: `backend/tests/test_cart.py`

**Interfaces:**
- Consumes: `PricingService`, `InventoryService`, `CatalogService`
- Produces: `Cart`：`id`(UUID)、`token`(UNIQUE str(64))、`region_code`、`currency_code`、`status`、`expires_at`；`CartLine`：`id`、`cart_id`、`variant_id`、`quantity`、`unit_price`(Money)、`currency_code`。`CartService(session)`：`create(region_code, currency_code) -> Cart`、`get_by_token(token) -> Cart`（过期抛 `CartExpiredError`）、`add_line(token, variant_id, qty) -> Cart`、`update_line(token, line_id, qty) -> Cart`（qty=0 即删除）、`remove_line(token, line_id) -> Cart`、`totals(token, region) -> PriceBreakdown`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_add_line_snapshots_unit_price(db_session):
    cart = await svc.create("us", "USD")
    cart = await svc.add_line(cart.token, variant.id, 2)
    assert cart.lines[0].unit_price == Decimal("19.99")   # 入库时快照

@pytest.mark.anyio
async def test_expired_cart_raises(db_session):
    with pytest.raises(CartExpiredError):
        await svc.get_by_token(expired_cart.token)

@pytest.mark.anyio
async def test_update_line_to_zero_removes_it(db_session):
    cart = await svc.update_line(cart.token, line.id, 0)
    assert cart.lines == []
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — `token` 用 `secrets.token_urlsafe(32)`；`expires_at = now + 30 days`；`add_line` 时调 `PricingService.unit_price` 快照；已存在同 variant 则累加数量。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add cart domain with price snapshot and expiry"`

---

## Task 11: Order 与状态机

**Files:**
- Create: `backend/app/domain/order/{models,repository,service,state_machine,schemas}.py`
- Test: `backend/tests/test_order.py`

**Interfaces:**
- Consumes: `CartService`, `InventoryService`, `PricingService`, `PaymentProvider`
- Produces:
  - `Order`：`id`、`number`(UNIQUE)、`status`、`region_code`、`currency_code`、`email`、`shipping_address`(JSONB)、`subtotal`、`shipping_fee`、`tax`、`total`、`idempotency_key`(UNIQUE, nullable)、`created_at`
  - `OrderLine`：`order_id`、`variant_id`、`product_name`、`variant_label`、`sku`、`unit_price`、`quantity`、`line_total`、`currency_code`
  - `OrderEvent`：`order_id`、`from_status`、`to_status`、`note`、`created_at`
  - `OrderStatus`（StrEnum）：`draft, awaiting_payment, paid, fulfilled, completed, cancelled, refunded`
  - `ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]]`
  - `Order.mark_paid()/mark_fulfilled()/mark_completed()/cancel()/refund()` — 非法流转抛 `DomainError(code="INVALID_STATUS_TRANSITION")`
  - `OrderService(session)`：`checkout(cart_token, email, shipping_address, idempotency_key=None) -> Order`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_checkout_snapshots_lines(db_session):
    o = await svc.checkout(cart.token, "a@b.c", addr)
    assert o.lines[0].product_name == "Neon Tee"
    # 改商品名后订单不变
    product.translations["en"].name = "Renamed"
    await db_session.commit()
    o2 = await svc.get(o.number)
    assert o2.lines[0].product_name == "Neon Tee"

@pytest.mark.anyio
async def test_checkout_is_idempotent(db_session):
    o1 = await svc.checkout(cart.token, "a@b.c", addr, idempotency_key="k1")
    o2 = await svc.checkout(cart.token, "a@b.c", addr, idempotency_key="k1")
    assert o1.id == o2.id

@pytest.mark.anyio
async def test_invalid_transition_rejected(db_session):
    o = await svc.checkout(cart.token, "a@b.c", addr)
    with pytest.raises(DomainError) as e:
        o.mark_fulfilled()          # draft/awaiting_payment 不能直接 fulfilled
    assert e.value.code == "INVALID_STATUS_TRANSITION"

@pytest.mark.anyio
async def test_checkout_decrements_stock(db_session):
    before = await InventoryService(db_session).available(variant.id)
    await svc.checkout(cart.token, "a@b.c", addr)
    assert await InventoryService(db_session).available(variant.id) == before - 2
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — `checkout` 流程（单事务）：解析 cart → `pricing.calculate` → 生成 `number`（`NS-{YYMMDD}-{6位随机}`，冲突重试 3 次）→ 快照订单行 → 预占库存 → 落 `draft` → 调 `payment.create_intent` → 置 `awaiting_payment`。`idempotency_key` 命中已有订单则直接返回。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add order aggregate with state machine, snapshot and idempotency"`

---

## Task 12: 支付适配器

**Files:**
- Create: `backend/app/domain/payment/{base,mock,service}.py`
- Test: `backend/tests/test_payment.py`

**Interfaces:**
- Produces: `PaymentIntent`（`provider`、`provider_ref`、`amount`、`currency`、`status`）；`PaymentResult`（`success: bool`、`provider_ref`、`raw: dict`）；`PaymentProvider`（ABC，方法 `async create_intent(order) -> PaymentIntent`、`async confirm(provider_ref) -> PaymentResult`、`async refund(provider_ref, amount) -> PaymentResult`）；`MockPaymentProvider`（`create_intent` 返回 `status="requires_confirmation"`；`confirm` 恒成功）；`get_payment_provider(code: str) -> PaymentProvider` 工厂，未注册 code 抛 `DomainError(code="UNKNOWN_PAYMENT_PROVIDER")`。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_mock_provider_confirm_succeeds():
    p = MockPaymentProvider()
    intent = await p.create_intent(order)
    assert intent.status == "requires_confirmation"
    assert (await p.confirm(intent.provider_ref)).success is True

def test_unknown_provider_raises():
    with pytest.raises(DomainError) as e:
        get_payment_provider("stripe")
    assert e.value.code == "UNKNOWN_PAYMENT_PROVIDER"
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — 接口签名按真实网关形态设计（意图 → 确认 → 退款），`provider_ref` 为不透明字符串。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add payment provider abstraction with mock implementation"`

---

## Task 13: Storefront API

**Files:**
- Create: `backend/app/api/v1/store/{locales,regions,products,carts,checkout,orders}.py`；Modify: `backend/app/api/v1/router.py`、`backend/app/core/deps.py`
- Test: `backend/tests/test_store_api.py`

**Interfaces:**
- Consumes: 全部 domain service
- Produces: `app/core/deps.py` 提供 `get_locale(request) -> str`（`?locale=` → `Accept-Language` → 默认）、`get_region(request) -> str`（`?region=` → `X-Region` → 默认）、`get_cart_token(request) -> str | None`。路由：
  - `GET /api/v1/store/locales`、`GET /api/v1/store/regions`
  - `GET /api/v1/store/products?category=&limit=&offset=&sort=` → 列表 + `X-Total-Count` 头
  - `GET /api/v1/store/products/{slug}`
  - `POST /api/v1/store/carts`、`GET /api/v1/store/carts/{token}`、`POST /api/v1/store/carts/{token}/lines`、`PATCH /api/v1/store/carts/{token}/lines/{line_id}`、`DELETE /api/v1/store/carts/{token}/lines/{line_id}`
  - `POST /api/v1/store/checkout`（需 `Idempotency-Key` 头，可选）
  - `GET /api/v1/store/orders/{number}`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_list_products_respects_locale_and_returns_total(client):
    r = await client.get("/api/v1/store/products?locale=en", headers={"X-Region": "us"})
    assert r.status_code == 200
    assert r.headers["X-Total-Count"] == "3"
    assert r.json()[0]["name"] == "Neon Tee"

@pytest.mark.anyio
async def test_cart_line_flow(client):
    r = await client.post("/api/v1/store/carts", json={"region": "us"})
    token = r.json()["token"]
    r = await client.post(f"/api/v1/store/carts/{token}/lines", json={"variant_id": str(v_id), "quantity": 2})
    assert r.json()["lines"][0]["quantity"] == 2

@pytest.mark.anyio
async def test_checkout_returns_order_and_is_idempotent(client):
    h = {"Idempotency-Key": "abc"}
    body = {"cart_token": token, "email": "a@b.c", "shipping_address": {...}}
    a = await client.post("/api/v1/store/checkout", json=body, headers=h)
    b = await client.post("/api/v1/store/checkout", json=body, headers=h)
    assert a.json()["number"] == b.json()["number"]
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — 依赖注入组装 service；响应模型用 Pydantic `Read` schema；设置 `Content-Language` 与 `X-Currency` 响应头；`GET /store/products` 组装 `X-Total-Count`。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add storefront api with locale, region and cart negotiation"`

---

## Task 14: Admin API 与鉴权

**Files:**
- Create: `backend/app/core/security.py`、`backend/app/api/v1/admin/{auth,products,categories,orders,inventory,settings}.py`；Modify: `backend/app/api/v1/router.py`
- Test: `backend/tests/test_admin_api.py`

**Interfaces:**
- Produces: `app.core.security`：`hash_password`、`verify_password`、`create_access_token(sub, role)`、`decode_token(token)`、`AdminUser` 模型（`email`、`password_hash`、`role`、`is_active`）、依赖 `require_admin`（校验 `Authorization: Bearer`，失败 401 `{"error":{"code":"UNAUTHORIZED"}}`）。路由：
  - `POST /api/v1/admin/auth/login` → `{"access_token", "token_type": "bearer"}`
  - `GET|POST|PATCH|DELETE /api/v1/admin/products[/{id}]`（含 `translations: dict[locale, {...}]` 批量提交）
  - `GET|POST|PATCH|DELETE /api/v1/admin/categories[/{id}]`
  - `GET /api/v1/admin/orders?status=&limit=&offset=`、`GET /api/v1/admin/orders/{id}`、`PATCH /api/v1/admin/orders/{id}/status`
  - `POST /api/v1/admin/inventory/{variant_id}/adjust`（body `{"delta": int, "reason": str}`）
  - `GET /api/v1/admin/settings/locales`、`GET /api/v1/admin/settings/currencies`、`GET /api/v1/admin/settings/regions`、`POST /api/v1/admin/settings/exchange-rates/refresh`

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_admin_endpoints_require_token(client):
    assert (await client.get("/api/v1/admin/products")).status_code == 401

@pytest.mark.anyio
async def test_login_then_crud_product(client):
    t = (await client.post("/api/v1/admin/auth/login", json={"email": "admin@x", "password": "admin123"})).json()["access_token"]
    h = {"Authorization": f"Bearer {t}"}
    r = await client.post("/api/v1/admin/products", json={"base_price": "19.99", "status": "published",
        "translations": {"zh-CN": {"name": "霓虹 T 恤", "slug": "neon-tee"}, "en": {"name": "Neon Tee", "slug": "neon-tee"}}}, headers=h)
    assert r.status_code == 201

@pytest.mark.anyio
async def test_order_status_transition_via_api(client, admin_headers, order):
    r = await client.patch(f"/api/v1/admin/orders/{order.id}/status", json={"status": "paid"}, headers=admin_headers)
    assert r.json()["status"] == "paid"
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — 密码用 `passlib`/`bcrypt`；JWT `HS256`，`exp` 24h；商品创建时按 `translations` 逐 locale upsert 翻译行。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add admin api with jwt auth and localized product crud"`

---

## Task 15: 种子数据与汇率定时任务

**Files:**
- Create: `backend/app/seed.py`、`backend/app/worker.py`（arq settings + cron `refresh_rates` 每 6 小时）
- Test: `backend/tests/test_seed.py`

**Interfaces:**
- Produces: `python -m app.seed` 幂等灌入：locales `zh-CN`(默认)/`en`；currencies `USD`(默认)/`CNY`/`EUR`；regions `us`(USD, 默认)/`cn`(CNY)；admin 用户 `admin@neostore.local` / `admin123`；3 个已发布商品（各 2 个 locale 翻译、2 个变体、库存 50）；初始汇率 1 USD = 7.25 CNY / 0.92 EUR。

- [ ] **Step 1: 写失败测试**

```python
@pytest.mark.anyio
async def test_seed_is_idempotent(db_session):
    from app.seed import run_seed
    await run_seed(db_session); await run_seed(db_session)
    assert await count(db_session, Locale) == 2
    assert await count(db_session, Product) == 3
```

- [ ] **Step 2: 跑测试确认失败** — Expected: FAIL
- [ ] **Step 3: 写实现** — 用 `INSERT ... ON CONFLICT DO NOTHING` / 先查后插，保证可重复执行。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: 起容器灌数据验证**

Run: `docker compose exec api python -m app.seed && curl -s 'localhost:8000/api/v1/store/products?locale=en' -H 'X-Region: us' | head -c 400`
Expected: 返回 3 个商品的 JSON

- [ ] **Step 6: Commit** — `git commit -m "feat: add idempotent seed data and hourly-safe arq worker"`

---

## Task 16: Next.js 顾客端

**Files:**
- Create: `storefront/{package.json,next.config.ts,tailwind.config.ts,tsconfig.json}`、`storefront/src/middleware.ts`、`storefront/src/app/layout.tsx`、`storefront/src/app/[locale]/(shop)/{page.tsx,products/page.tsx,products/[slug]/page.tsx,cart/page.tsx,checkout/page.tsx}`、`storefront/src/lib/{api.ts,format.ts}`、`storefront/src/components/{ProductCard,LocaleSwitcher,CurrencySwitcher,Header,CartBadge}.tsx`、`storefront/src/app/{sitemap.ts,robots.ts}`、`storefront/Dockerfile`
- Test: `storefront/e2e/smoke.spec.ts`（Playwright）

**Interfaces:**
- Consumes: Storefront API 全部端点
- Produces: `lib/api.ts` 导出 `getLocales()`、`getRegions()`、`getProducts({locale, region, ...})`、`getProduct(slug, {locale, region})`、`createCart(region)`、`addLine(token, variantId, qty)`、`checkout(token, email, address, idempotencyKey)`；类型由 `npm run gen:types`（`openapi-typescript http://localhost:8000/openapi.json -o src/lib/api-types.ts`）生成。

- [ ] **Step 1: 写失败测试** — `e2e/smoke.spec.ts`：访问 `/en`，断言商品列表出现、切换 `/zh-CN` 后商品名变成中文、加购后购物车角标为 1。
- [ ] **Step 2: 跑测试确认失败** — Run: `npx playwright test`；Expected: FAIL
- [ ] **Step 3: 写实现** — `middleware.ts` 做 locale 检测（路径前缀 → cookie → `Accept-Language` → 默认 `zh-CN`）；商品页用 Server Component 直连 API，`export const revalidate = 60`；`generateMetadata` 输出 title/description/OG/hreflang 与 JSON-LD；配色按 Global Constraints 的深色 + 霓虹渐变。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add nextjs storefront with i18n routing, seo and cart flow"`

---

## Task 17: 管理后台前端

**Files:**
- Create: `admin/{package.json,vite.config.ts,tsconfig.json,index.html}`、`admin/src/{main.tsx,App.tsx,lib/api.ts,lib/auth.ts}`、`admin/src/pages/{Login,ProductList,ProductEdit,OrderList,OrderDetail,Inventory,Settings}.tsx`、`admin/Dockerfile`
- Test: `admin/src/__tests__/product-edit.test.tsx`（Vitest + Testing Library）

**Interfaces:**
- Consumes: Admin API
- Produces: `lib/api.ts` 带 token 注入与 401 拦截跳登录；商品编辑页用 Tab 按 locale 分组编辑 `translations`，一次提交。

- [ ] **Step 1: 写失败测试** — 渲染 `ProductEdit`，切换 locale Tab 后表单显示对应语言的 name/slug 字段。
- [ ] **Step 2: 跑测试确认失败** — Run: `npm test`；Expected: FAIL
- [ ] **Step 3: 写实现** — TanStack Query 管数据、TanStack Table 管列表、react-hook-form + zod 管表单；订单页提供状态流转按钮，只展示 `ALLOWED_TRANSITIONS` 允许的目标状态。
- [ ] **Step 4: 跑测试确认通过** — Expected: PASS
- [ ] **Step 5: Commit** — `git commit -m "feat: add admin dashboard with localized product editing and order ops"`

---

## Task 18: 全链路验证与文档

**Files:**
- Create: `README.md`（重写）、`docs/RUNBOOK.md`、`scripts/smoke.sh`
- Test: `scripts/smoke.sh`

- [ ] **Step 1: 写冒烟脚本**

`scripts/smoke.sh`：起全栈 → 等 `/readyz` → 登录后台 → 建一个商品 → 前台用英文查到它 → 加购 → 下单 → 断言订单号返回 → 断言库存减 1。任一步失败 `exit 1`。

- [ ] **Step 2: 跑脚本确认失败** — Run: `bash scripts/smoke.sh`；Expected: 在某一步失败（脚本刚写、服务未全起）
- [ ] **Step 3: 修到通过** — 逐项排查直至脚本全绿。
- [ ] **Step 4: 写文档** — `README.md`：架构图、目录说明、`docker compose up` 起服务、种子账号、环境变量清单、常用命令。`docs/RUNBOOK.md`：迁移、备份恢复、汇率源更换、支付网关接入步骤（按 `PaymentProvider` 接口实现新类并注册到工厂）。
- [ ] **Step 5: Commit** — `git commit -m "docs: add end-to-end smoke script, readme and runbook"`

---

## Self-Review

**Spec 覆盖核对**

| Spec 章节 | 对应 Task |
|---|---|
| §3 目录结构与分层约束 | T1–T2（domain 禁 import fastapi 由 ruff 规则 + review 保证） |
| §4.1 多语言 | T4、T7、T13、T14 |
| §4.2 多币种 | T5、T8 |
| §4.3 Region | T6 |
| §4.4 Catalog | T7 |
| §4.5 Cart/Order | T10、T11 |
| §4.6 库存防超卖 | T9 |
| §4.7 定价单一入口 | T8 |
| §5 API 约定（幂等/错误体/分页/语言区域协商） | T3、T13 |
| §6.1 storefront（SEO/hreflang/sitemap/middleware） | T16 |
| §6.2 admin | T14、T17 |
| §7 基础设施与部署 | T1、T15、T18 |
| §8 错误处理 | T3 |
| §9 测试策略（换算/并发/i18n 回退/幂等/快照） | T5、T8、T9、T11、T4 |
| §12 汇率 API | T5、T15 |
| §12 支付适配器 | T12 |

无遗漏。

**占位符扫描**：无 TBD / TODO / "类似 Task N"。每个 Task 均给出精确路径、接口签名与关键代码。

**类型一致性**：`round_money`（T5 定义）在 T8 使用；`InsufficientStockError`（T3 定义）在 T9 使用；`CartExpiredError`（T3）在 T10 使用；`DomainError(code="INVALID_STATUS_TRANSITION")` / `UNKNOWN_PAYMENT_PROVIDER`（T11/T12）均为 `DomainError` 子形态而非新类，与 T3 定义一致；`PriceBreakdown`（T8）在 T10/T11 使用；`PaymentProvider`（T12）在 T11 的 `checkout` 中被调用——T11 的 `OrderService` 构造参数需接收 `PaymentProvider`，已在 T11 Interfaces 的 Consumes 中标注。
