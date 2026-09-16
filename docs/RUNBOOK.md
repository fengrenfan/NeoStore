# RUNBOOK

NeoStore 的运维手册。日常操作、出事时怎么办、以及三个"接真实外部服务"的口子怎么改。

约定：
- 所有后端命令在 `backend/` 下执行，`alembic` 与 `python` 都指容器内或 `.venv` 里的那一个。
- 容器里的等价值：`docker compose exec api <命令>`。

---

## 0. 访问入口

| 面 | 地址 | 说明 |
|---|---|---|
| 顾客端 | <https://store.xiaodigua.shop> | Next.js storefront；`/` 会 307 跳到 locale 前缀（`/zh-CN`、`/en`…） |
| **管理后台** | <https://store.xiaodigua.shop/admin/> | Vite SPA，入口标题「NeoStore 控制台」。深链由 nginx 回退到 `index.html`，未登录会停在 `/admin/login` |
| API | `https://store.xiaodigua.shop/api/v1/...` | 与前台同源；所以生产镜像的 `NEXT_PUBLIC_API_BASE_URL` 故意留空 |
| 健康检查 | `/healthz`、`/readyz` | 挂在 Caddy 根路径，**不带** `/api` 前缀 |

上线路径：宿主 nginx（80/443，certbot 证书）→ `127.0.0.1:8091` Caddy → 按前缀分流到
`/api` → api、`/admin` → admin、其余 → storefront。Caddy 是唯一入口，不要绕过它直连容器端口。

不对外、仅本机可达的调试端口：`8091` Caddy、`3002` storefront、`8092` admin、`18082` api。

**后台凭据不在仓库里**：管理员账号与密码来自 `backend/.env`（服务器专属、已 gitignore）的
`SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD`，只种一次。取回：

```bash
ssh <server> 'grep -E "^SEED_ADMIN" /home/app/store/backend/.env'
```

首次登录后请在后台改掉密码（上线检查清单里有这一条）。

---

## 1. 发布与迁移

### 发布一个新版本

```bash
git pull
docker compose build            # 只改了某一块就 build 对应服务
docker compose up -d
docker compose ps               # 确认都 healthy / 没有 restarting
curl -fsS localhost/readyz      # 经 Caddy 探活
```

`api` 容器的启动命令会先跑 `alembic upgrade head`，再跑一次幂等的种子脚本，最后才起 uvicorn。所以**迁移是随发布自动做的**，不需要单独一步。

### 迁移原则

| 情况 | 做法 |
|---|---|
| 加表 / 加可空列 | 直接上，向前兼容 |
| 加非空列 | 分两次发：先加可空列 → 回填 → 再改成非空 |
| 删列 / 改名 | 别在同一版里删。先让代码不读它，发一版，下一版再删 |
| 数据回填 | 写成独立迁移或一次性脚本，不要塞在 `alembic upgrade` 里跑长事务 |

生成迁移：

```bash
cd backend
alembic revision --autogenerate -m "add wishlist table"
git diff alembic/versions/        # 一定人工过一遍：autogenerate 会漏掉枚举变更与索引选项
alembic upgrade head
```

`tests/test_migrations.py` 会校验模型与迁移没有漂移——改了模型忘了生成迁移，这个测试会红。

### 回滚

```bash
alembic downgrade -1              # 退一版
alembic history --verbose         # 看链条
```

**先备份再回滚**（见第 2 节）。降级脚本只保证结构回退，不保证数据回来：删掉的列回不来。

### 迁移版本对不上时

`alembic current` 与 `alembic heads` 不一致，通常是两个分支各自生成了迁移：

```bash
alembic merge -m "merge heads" <rev1> <rev2>
```

---

## 2. 备份与恢复

### 备份

```bash
# 结构 + 数据，自定义格式（推荐：可并行恢复、可选择性恢复）
docker compose exec -T db pg_dump -U neostore -Fc neostore > backup-$(date +%F-%H%M).dump

# 纯 SQL，方便肉眼检查与手工改
docker compose exec -T db pg_dump -U neostore neostore | gzip > backup-$(date +%F).sql.gz
```

顺带备份 `backend/.env`（含 `JWT_SECRET`）。丢了它所有已签发的 token 立即失效，所有人都要重新登录。

### 恢复

```bash
docker compose stop api worker            # 断掉写入方，否则会边恢复边被写
docker compose exec -T db dropdb -U neostore neostore
docker compose exec -T db createdb -U neostore neostore
docker compose exec -T db pg_restore -U neostore -d neostore --clean --if-exists < backup.dump
docker compose start api worker
```

恢复后务必核对：`GET /readyz`、后台订单列表能打开、随便挑一笔历史订单看金额是否还是快照里的值。

### 只恢复某张表

```bash
docker compose exec -T db pg_restore -U neostore -d neostore -t orders --data-only < backup.dump
```

注意外键顺序：`orders` 依赖 `region`/`currency`；`order_line`、`order_event` 依赖 `orders`。按依赖从上游往下恢复。

---

## 3. 更换汇率源

汇率只在**没有显式定价时**作为兜底，且只被 worker 刷新，请求路径上永远不 fetch。所以换源是低风险操作。

汇率源的接口在 `app/integrations/exchange_rate.py`：`ExchangeRateProvider.fetch(base) -> {quote: rate}`（`1 base == rate quote`）。要换源就新写一个类：

```python
# app/integrations/exchange_rate.py
class MyRateProvider(ExchangeRateProvider):
    name = "my-provider"

    async def fetch(self, base: str) -> dict[str, Decimal]:
        ...
        return {"CNY": Decimal("7.18"), ...}
```

然后把工厂指过去：

```python
def get_exchange_rate_provider() -> ExchangeRateProvider:
    return MyRateProvider(...)          # 原来是 OpenExchangeRateProvider
```

三条硬性约定：

1. **失败必须抛 `ExchangeRateUnavailableError`，不许返回空字典。** `CurrencyService` 只在 fetch 成功时写库，失败时保留上一次的汇率——最坏情况是价格旧一点，而不是结账挂掉。
2. **返回 `Decimal`**，不要 `float`。`OpenExchangeRateProvider` 里 `Decimal(str(value))` 就是这个原因。
3. 新增的 quote 币种要在 `currency` 表里有对应行，否则定价算不到它。

改完：

```bash
docker compose restart worker
docker compose logs -f worker          # 看到 "refreshed N exchange rates against USD"
```

手动触发一次、或临时人工指定某个货币对：

- 后台 → 设置 → 汇率 → 「拉取最新汇率」（`POST /api/v1/admin/settings/exchange-rates/refresh`）
- 人工写入（`source=manual`）用于 provider 覆盖不到的货币对；人工写入不会被下一次自动刷新抹掉。

**观察点**：`exchange_rate` 表的 `fetched_at` 是否持续推进。停了就是源挂了或 worker 挂了，此时顾客端看到的换算价会是旧的——不报错，但要有告警。

---

## 4. 接入真实支付网关

现在是 `MockPaymentProvider`：结账时创建 intent，`POST /store/orders/{number}/pay` 用替代真实回调，把订单推到 `paid` 并**提交预占库存**。

接真实网关分四步，`OrderService` 一行都不用改——它只依赖抽象基类。

### 步骤 1：实现 `PaymentProvider`

`app/domain/payment/base.py` 定义了三个方法：

```python
class PaymentProvider(ABC):
    code: str = "base"

    async def create_intent(self, order: Order) -> PaymentIntent: ...
    async def confirm(self, provider_ref: str) -> PaymentResult: ...
    async def refund(self, provider_ref: str, amount: Decimal) -> PaymentResult: ...
```

- `create_intent` 在 `checkout()` 里被调用，返回的引用会被写进 `order_event.note = "intent:<ref>"`——**确认阶段就是从这里把引用找回来的**，所以引用必须能持久化、能回查。
- `confirm` 里调用网关的"捕获/查询"接口，成功返回 `PaymentResult(success=True, ...)`。
- 金额从 `order.total` / `order.currency_code` 取，不要在网关适配器里重算。

放在 `app/domain/payment/<provider>.py`，参考 `mock.py` 的写法（它是内存实现，真实实现要注意**幂等**：同一 `provider_ref` 收到两次 `confirm` 必须都返回成功，因为 webhook 会重投）。

### 步骤 2：注册

```python
# app/domain/payment/<provider>.py 末尾
register_provider(StripePaymentProvider(api_key=settings.stripe_secret_key))
```

像 `mock.py` 最后那行 `register_provider(MockPaymentProvider())` 一样。注册后 `get_payment_provider("stripe")` 就能用了；未知 code 会抛 `UNKNOWN_PAYMENT_PROVIDER`（400，`details.available` 列出可选项）。

下单时选网关：`POST /api/v1/store/checkout` 的 body 带 `payment_provider: "stripe"`，不传默认 `mock`。

### 步骤 3：把确认路径从"替代接口"换成 webhook

这是唯一需要动路由的一步。新加一个 webhook 路由（**不要**复用 `/store/orders/{n}/pay`）：

```python
# app/api/v1/store/payments.py（新增）
@router.post("/payments/{provider}/webhook")
async def webhook(provider: str, request: Request, session: SessionDep, orders: OrderDep):
    raw = await request.body()
    signature = request.headers.get("stripe-signature", "")
    if not verify_signature(raw, signature):        # 必须验签
        raise UnauthorizedError(...)
    payload = json.loads(raw)
    await orders.pay(payload["order_number"], provider_code=provider)
    await session.commit()
    return {"received": True}
```

要点：

1. **必须验签**，并且用**原始 body** 验（重新序列化 JSON 会改字节，签名一定不过）。
2. 处理**重投**：订单已经是 `paid` 时 `mark_paid` 会抛 `InvalidStatusTransitionError`（409）。webhook 里要把这个当成"已处理成功"返回 2xx，否则网关会一直重试。
3. webhook 要**先入队再回 2xx**（如果处理慢），或者保证处理足够快，别让网关超时。
4. 网关返回的金额、币种与 `order.total` 对不上时，**拒绝确认并告警**，这是最常见的攻击面。

### 步骤 4：关掉演示接口

```bash
# .env / compose
ENABLE_MOCK_PAYMENTS=false
```

关掉之后 `/api/v1/store/orders/{number}/pay` 直接返回 **404 `MOCK_PAYMENTS_DISABLED`**——不是 403，就是让它看起来不存在。`tests/test_api_store.py::test_mock_payment_route_vanishes_when_disabled` 盯着这个行为。

顺带收尾：

- 顾客端 `PayButton` / `CheckoutView` 要改成跳网关托管页，订单页不再有"模拟支付"按钮。
- 订单状态机不能改：`awaiting_payment → paid` 仍然由 webhook 驱动，`mark_paid()` 仍然提交预占库存。
- 退款走 `allowed_targets()` 允许的目标：`order.refund(note)` 把订单推到 `refunded`，**不要手改 `status` 字段**。
- **已知缺口**：`OrderService.transition(..., REFUNDED)` 目前只流转状态，并没有回调 `PaymentProvider.refund()`——接真实网关时要把这一步补上，否则订单显示已退款而钱没退。补的时候注意：先调网关、成功后再流转状态；网关调用失败就保持订单不动并报错，不要出现"状态说退了、钱没退"的中间态。

---

## 5. 日常排查

| 症状 | 先看哪里 |
|---|---|
| 后台打不开 / 一直跳登录 | 浏览器 localStorage 里的 token 是否被清；`/api/v1/admin/auth/me` 直接 curl 一次看是否 401；换了 `JWT_SECRET` 会让所有旧 token 失效 |
| 下单报 409 `INVALID_STATUS_TRANSITION` | 订单已经被处理过了。查 `order_event` 看最后一次流转是谁做的 |
| 下单报 `INSUFFICIENT_STOCK` | 库存不够。看 `inventory_item` 的 `quantity/reserved`——`reserved` 是未支付的预占，会随取消释放 |
| 价格/库存数字不对 | 后台 → 商品 → 变体与定价，看有没有显式定价；显式定价优先于汇率换算 |
| 顾客端显示旧价格 | 商品/地区相关页面是 `force-dynamic`（跟地区 cookie 走），但 API 侧的价格来自数据库——确认后台改的是同一个变体 |
| 页面文案没跟着语言变 | `locale` 表里有没有这个语言；`NEXT_PUBLIC_LOCALES` 是否包含它；缺翻译会按契约回退到默认语言，是设计行为不是 bug |
| 容器起来就退出 | `docker compose logs api`。常见是 `.env` 缺 `JWT_SECRET` 或数据库没连上 |

### 冒烟测试

```bash
bash scripts/smoke.sh                # 全链路
bash scripts/smoke.sh --api-only     # 只验后端
```

脚本自己起一套临时环境（SQLite + 三个端口），跑完关掉。它**会在端口被占用时直接退出**——这是刻意的：如果让一个残留的旧服务应答，所有断言都会"通过"，但描述的是另一个数据库。看到 `Refusing to run` 就先把占用者停掉。

每次运行用独立的数据库文件（`smoke-<pid>.db`），所以不会继承上一次的订单。

### 后台的浏览器级检查

`scripts/smoke.sh` 只验证后台的静态产物能被取到（shell、bundle、SPA fallback），不验证它跑起来对不对。要验证后者：

```bash
node scripts/admin-check.cjs http://127.0.0.1:5173/admin <一个待支付订单号>
```

它会开一个真实 Chromium，走一遍「登录 → 概览 → 商品 → 库存调整 → 设置 → 订单状态流转」，任何 console 报错、失败请求或断言不过都会让退出码变非零，截图落在 `/tmp/neostore-admin-shots/`。

需要 Playwright（`PLAYWRIGHT_MODULE` 可指定路径）；Chromium 会先在 Playwright 缓存里找一个能用的，找不到再让 Playwright 自己决定，也可以用 `CHROMIUM_PATH` 指定。它**不在** `smoke.sh` 里自动跑：它依赖 Playwright，而 CI 上通常没有。

### 清库重来（仅限本地）

```bash
docker compose down -v               # -v 会删掉 pgdata，数据不可恢复
docker compose up --build
```

---

## 6. 上线前检查清单

- [ ] `JWT_SECRET` 换成随机值（`openssl rand -hex 32`）
- [ ] `SEED_ADMIN_PASSWORD` 换掉，且已登录后台改过密码
- [ ] `ENABLE_MOCK_PAYMENTS=false`
- [ ] Caddyfile 的站点地址改成真实域名（现在是 `:80` 本地入口），TLS 会自动签发
- [ ] `NEXT_PUBLIC_SITE_URL` 指向真实域名（影响 canonical / hreflang / sitemap，构建期要重跑）
- [ ] `CORS_ORIGINS` 只留真实前端域名
- [ ] 数据库备份有定时任务，且**试过一次恢复**
- [ ] `curl -fsS <域名>/readyz` 与 `/healthz` 都通
- [ ] 后台 `/admin/` 能登录，顾客端首页、商品页、结账在真实域名下走通一次
