#!/usr/bin/env bash
#
# End-to-end smoke test for NeoStore.
#
# Runs the whole purchase loop against a throwaway SQLite database — no Docker,
# no PostgreSQL — so it works on a laptop and in CI:
#
#   storefront → API → cart → checkout → payment → order
#
# The storefront leg prefers the standalone server (`node .next/standalone/
# server.js`), which is the artifact the container runs; it falls back to
# `next start`, and is skipped entirely when the storefront has not been built.
#
# The admin leg serves the built bundle through `vite preview`, which is the
# closest thing to nginx without Docker: same base path, same SPA fallback.
#
# Usage:
#   scripts/smoke.sh              # full stack
#   scripts/smoke.sh --api-only   # skip both frontends
#
# Ports are overridable so this never fights a running dev server.

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
STOREFRONT="$ROOT/storefront"
ADMIN="$ROOT/admin"

API_PORT="${API_PORT:-8010}"
WEB_PORT="${WEB_PORT:-3110}"
ADMIN_PORT="${ADMIN_PORT:-3111}"
API_BASE="http://127.0.0.1:${API_PORT}"
WEB_BASE="http://127.0.0.1:${WEB_PORT}"
ADMIN_BASE="http://127.0.0.1:${ADMIN_PORT}"

# A fresh file per run, rather than deleting a shared one.
#
# The shared name was a trap: if the delete did not land — a denied unlink, a
# leftover `-wal`, an unrelated server still holding the old inode — the run
# silently inherited a previous run's orders and every assertion described
# something that had already happened. A unique name cannot inherit anything.
RUN_ID="$$"
DB_FILE="$BACKEND/smoke-${RUN_ID}.db"
DB_URL="sqlite+aiosqlite:///./smoke-${RUN_ID}.db"

# The sandbox here sets a proxy that cannot reach localhost.
CURL=(curl -sS --noproxy '*' --max-time 20)

PYTHON="$BACKEND/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON="$(command -v python3)"
NODE="$(command -v node)"

API_PID=""
WEB_PID=""
ADMIN_PID=""
FAILURES=0
SKIP_WEB=0
[[ "${1:-}" == "--api-only" ]] && SKIP_WEB=1

# Servers are launched as direct background jobs so `$!` is the real PID and
# `kill` actually reaches them. Nothing here calls a bare `wait`: a bare `wait`
# blocks on processes that outlive their subshell, which turns a finished test
# into a hung one.
cleanup() {
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null
  [[ -n "$WEB_PID" ]] && kill "$WEB_PID" 2>/dev/null
  [[ -n "$ADMIN_PID" ]] && kill "$ADMIN_PID" 2>/dev/null
  for _ in 1 2 3 4 5; do sleep 0.2; done

  # Best effort: the database is disposable, and a leftover file is harmless
  # now that each run gets its own name.
  rm -f "$DB_FILE" "$DB_FILE-wal" "$DB_FILE-journal" 2>/dev/null

  # A server that outlived the run would be picked up by the next one — and
  # answer for it. Say so rather than leaving a landmine behind.
  for pair in "$API_PORT:api" "$WEB_PORT:storefront" "$ADMIN_PORT:admin"; do
    port="${pair%%:*}"
    if port_is_busy "$port"; then
      echo "  warning: something is still listening on $port (${pair##*:})" >&2
    fi
  done
  return 0
}
trap cleanup EXIT

pass() { printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m  %s\n' "$1"; FAILURES=$((FAILURES + 1)); }
info() { printf '\n\033[1m%s\033[0m\n' "$1"; }

# Ports are probed with a socket rather than `lsof`, which is absent on plenty
# of CI images.
port_is_busy() {
  "$PYTHON" -c '
import socket, sys
s = socket.socket()
s.settimeout(0.5)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
' "$1" 2>/dev/null
}

# Starting next to a stranger's server is the worst failure mode this script
# has: every request succeeds and every assertion describes the wrong process.
require_free_ports() {
  local busy=0
  for port in "$@"; do
    if port_is_busy "$port"; then
      echo "  port $port is already in use" >&2
      busy=1
    fi
  done
  if [[ "$busy" == "1" ]]; then
    cat >&2 <<'MSG'
  Refusing to run: the ports above are taken, and a stale server would happily
  answer every request below while describing a different database.

  Stop it (`lsof -nP -iTCP:8010 -sTCP:LISTEN` finds it), or pick other ones:
      API_PORT=9010 WEB_PORT=9110 ADMIN_PORT=9111 scripts/smoke.sh
MSG
    exit 2
  fi
}

# Evaluate a Python expression against the parsed JSON, which is bound to `d`,
# e.g. `json "$body" "d['total']"` or `json "$body" "[r['code'] for r in d]"`.
json() {
  printf '%s' "$1" | "$PYTHON" -c \
    "import json,sys; d=json.load(sys.stdin); print(${2})" 2>/dev/null
}

expect_json() {
  local label="$1" body="$2" path="$3" expected="$4" actual
  actual="$(json "$body" "$path")"
  if [[ "$actual" == "$expected" ]]; then
    pass "$label"
  else
    fail "$label (expected '$expected', got '$actual')"
  fi
}

expect_http() {
  local label="$1" url="$2" expected="$3" method="${4:-GET}" code
  code="$("${CURL[@]}" -o /dev/null -w '%{http_code}' -X "$method" "$url")"
  if [[ "$code" == "$expected" ]]; then
    pass "$label"
  else
    fail "$label (expected HTTP $expected, got $code)"
  fi
}

wait_for() {
  local url="$1" name="$2" tries="${3:-60}"
  for _ in $(seq 1 "$tries"); do
    if "${CURL[@]}" -o /dev/null "$url" 2>/dev/null; then return 0; fi
    sleep 0.5
  done
  echo "  timed out waiting for $name at $url" >&2
  return 1
}

info "0. Checking the ports are ours to take"
if [[ "$SKIP_WEB" == "1" ]]; then
  require_free_ports "$API_PORT"
else
  require_free_ports "$API_PORT" "$WEB_PORT" "$ADMIN_PORT"
fi
pass "ports $API_PORT/$WEB_PORT/$ADMIN_PORT are free"

info "1. Seeding a throwaway SQLite database"
( cd "$BACKEND" && DATABASE_URL="$DB_URL" "$PYTHON" -m app.seed --create-all --skip-rates ) \
  | sed 's/^/     /' || { echo "seed failed" >&2; exit 1; }

# The whole test is meaningless if the database already holds history, so the
# emptiness is asserted rather than assumed.
fresh_counts() {
  "$PYTHON" - "$DB_FILE" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
print(
    con.execute("select count(*) from orders").fetchone()[0],
    con.execute("select count(*) from product").fetchone()[0],
)
PY
}
read -r SEED_ORDERS SEED_PRODUCTS <<<"$(fresh_counts)"
if [[ "$SEED_ORDERS" == "0" && "$SEED_PRODUCTS" != "0" ]]; then
  pass "seeded database is fresh (0 orders, $SEED_PRODUCTS products)"
else
  fail "seeded database is not fresh (orders=$SEED_ORDERS products=$SEED_PRODUCTS)"
  exit 1
fi

info "2. Starting the API on :$API_PORT"
cd "$BACKEND"
DATABASE_URL="$DB_URL" "$PYTHON" -m uvicorn app.main:app \
  --host 127.0.0.1 --port "$API_PORT" --log-level warning \
  > /tmp/neostore-api.log 2>&1 &
API_PID=$!
# Kept out of the job table so bash does not echo a "Terminated" notice for a
# server we stopped on purpose.
disown
cd "$ROOT"
wait_for "$API_BASE/healthz" "the API" || exit 1
pass "GET /healthz is up"

if "${CURL[@]}" "$API_BASE/readyz" | grep -q '"status":"ok"'; then
  pass "GET /readyz reports ready"
else
  fail "GET /readyz did not report ready"
fi

info "3. Storefront reads"
if "${CURL[@]}" "$API_BASE/api/v1/store/locales" | grep -q '"zh-CN"'; then
  pass "GET /store/locales returns zh-CN"
else
  fail "GET /store/locales missing zh-CN"
fi

REGIONS="$("${CURL[@]}" "$API_BASE/api/v1/store/regions")"
expect_json "GET /store/regions lists cn priced in CNY" "$REGIONS" \
  "next(r['currency_code'] for r in d if r['code']=='cn')" "CNY"

PRODUCTS="$("${CURL[@]}" "$API_BASE/api/v1/store/products?limit=1")"
SLUG="$(json "$PRODUCTS" "d[0]['slug']")"
if [[ -n "$SLUG" ]]; then
  pass "GET /store/products lists '$SLUG'"
else
  fail "GET /store/products returned nothing"
  SLUG="neon-tee"
fi

DETAIL="$("${CURL[@]}" "$API_BASE/api/v1/store/products/$SLUG?locale=zh-CN")"
VARIANT_ID="$(json "$DETAIL" "d['variants'][0]['id']")"
ZH_NAME="$(json "$DETAIL" "d['name']")"
if [[ -n "$VARIANT_ID" && "$ZH_NAME" != "$SLUG" ]]; then
  pass "GET /store/products/$SLUG?locale=zh-CN is translated ($ZH_NAME)"
else
  fail "product detail did not come back translated"
fi

info "4. The purchase loop"
CART="$("${CURL[@]}" -X POST -H 'content-type: application/json' \
  -d '{"region":"cn"}' "$API_BASE/api/v1/store/carts")"
TOKEN="$(json "$CART" "d['token']")"
expect_json "POST /store/carts pinned the cn region" "$CART" "d['region_code']" "cn"

"${CURL[@]}" -X POST -H 'content-type: application/json' \
  -d "{\"variant_id\":\"$VARIANT_ID\",\"quantity\":2}" \
  "$API_BASE/api/v1/store/carts/$TOKEN/lines" >/dev/null

TOTALS="$("${CURL[@]}" "$API_BASE/api/v1/store/carts/$TOKEN/totals")"
TOTAL="$(json "$TOTALS" "d['total']")"
if [[ -n "$TOTAL" ]]; then
  pass "cart totals compute in CNY (total $TOTAL)"
else
  fail "cart totals did not compute"
fi

# Totals must not move just because a different region is requested: the cart
# was priced in CNY when it was created and stays there.
OTHER_TOTAL="$(json "$("${CURL[@]}" "$API_BASE/api/v1/store/carts/$TOKEN/totals?region=us")" "d['total']")"
if [[ "$OTHER_TOTAL" == "$TOTAL" ]]; then
  pass "totals ignore a different requested region"
else
  fail "totals changed with the request region ($TOTAL -> $OTHER_TOTAL)"
fi

CHECKOUT_BODY="{\"cart_token\":\"$TOKEN\",\"email\":\"smoke@neostore.local\",\
\"shipping_address\":{\"name\":\"Smoke Test\",\"line1\":\"1 Test Way\",\
\"city\":\"Shenzhen\",\"country\":\"CN\",\"postal_code\":\"518000\"}}"

ORDER="$("${CURL[@]}" -X POST -H 'content-type: application/json' \
  -H 'Idempotency-Key: smoke-key-1' -d "$CHECKOUT_BODY" \
  "$API_BASE/api/v1/store/checkout")"
ORDER_NUMBER="$(json "$ORDER" "d['number']")"
expect_json "POST /store/checkout awaits payment" "$ORDER" "d['status']" "awaiting_payment"

REPLAY_NUMBER="$(json "$("${CURL[@]}" -X POST -H 'content-type: application/json' \
  -H 'Idempotency-Key: smoke-key-1' -d "$CHECKOUT_BODY" \
  "$API_BASE/api/v1/store/checkout")" "d['number']")"
if [[ "$REPLAY_NUMBER" == "$ORDER_NUMBER" ]]; then
  pass "replayed checkout returns the same order (no double reservation)"
else
  fail "replayed checkout minted a second order"
fi

ORDER_TOTAL="$(json "$ORDER" "d['total']")"
if [[ "$ORDER_TOTAL" == "$TOTAL" ]]; then
  pass "order total matches the cart totals the shopper saw ($TOTAL)"
else
  fail "order total ($ORDER_TOTAL) differs from cart totals ($TOTAL)"
fi

# Naive timestamps read as *local* time in the browser, which silently shifts
# every displayed time by the viewer's offset.
expect_json "order timestamps carry a UTC offset" "$ORDER" \
  "d['events'][0]['created_at'].endswith('+00:00')" "True"

PAID="$("${CURL[@]}" -X POST "$API_BASE/api/v1/store/orders/$ORDER_NUMBER/pay")"
expect_json "mock payment confirms the order" "$PAID" "d['status']" "paid"
expect_http "paying twice is refused" \
  "$API_BASE/api/v1/store/orders/$ORDER_NUMBER/pay" 409 POST

info "5. Admin surface"
JWT="$(json "$("${CURL[@]}" -X POST -H 'content-type: application/json' \
  -d '{"email":"admin@neostore.local","password":"admin123"}' \
  "$API_BASE/api/v1/admin/auth/login")" "d['access_token']")"
if [[ -n "$JWT" ]]; then
  pass "admin login issues a token"
  "${CURL[@]}" -H "authorization: Bearer $JWT" \
    "$API_BASE/api/v1/admin/orders/$ORDER_NUMBER" >/dev/null \
    && pass "admin can read the order" \
    || fail "admin could not read the order"
else
  fail "admin login failed"
fi

expect_http "admin list rejects unauthenticated access" "$API_BASE/api/v1/admin/orders" 401

# The console reads these on every screen, so the shapes are worth pinning down
# here rather than discovering a missing field in the browser.
ADMIN_PRODUCTS="$("${CURL[@]}" -H "authorization: Bearer $JWT" \
  "$API_BASE/api/v1/admin/products?limit=1")"
expect_json "admin products expose variant availability" "$ADMIN_PRODUCTS" \
  "isinstance(d['items'][0]['variants'][0]['available'], int)" "True"

ADMIN_REGIONS="$("${CURL[@]}" -H "authorization: Bearer $JWT" \
  "$API_BASE/api/v1/admin/settings/regions")"
expect_json "admin regions carry currency and tax rate" "$ADMIN_REGIONS" \
  "next(r['currency_code'] for r in d if r['code']=='cn')" "CNY"

INVENTORY="$("${CURL[@]}" -H "authorization: Bearer $JWT" \
  "$API_BASE/api/v1/admin/inventory/$VARIANT_ID")"
BEFORE_QUANTITY="$(json "$INVENTORY" "d['quantity']")"
ADJUSTED="$("${CURL[@]}" -X POST -H 'content-type: application/json' \
  -H "authorization: Bearer $JWT" -d '{"delta":3,"reason":"manual","note":"smoke"}' \
  "$API_BASE/api/v1/admin/inventory/$VARIANT_ID/adjust")"
expect_json "admin inventory adjustment applies the delta" "$ADJUSTED" \
  "d['quantity']" "$((BEFORE_QUANTITY + 3))"

expect_http "admin settings reject unauthenticated access" \
  "$API_BASE/api/v1/admin/settings/locales" 401

info "6. Storefront rendering"
STANDALONE="$STOREFRONT/.next/standalone"
if [[ "$SKIP_WEB" == "1" ]]; then
  echo "  skipped (--api-only)"
elif [[ -f "$STANDALONE/server.js" ]]; then
  # The standalone bundle does not carry the static assets; the Dockerfile
  # copies them in, so the smoke test does the same rather than testing a
  # layout that never ships.
  cp -R "$STOREFRONT/.next/static" "$STANDALONE/.next/static" 2>/dev/null
  [[ -d "$STOREFRONT/public" ]] && cp -R "$STOREFRONT/public" "$STANDALONE/public" 2>/dev/null

  cd "$STANDALONE"
  PORT="$WEB_PORT" HOSTNAME=127.0.0.1 API_BASE_URL="$API_BASE" \
    NEXT_PUBLIC_API_BASE_URL="$API_BASE" NEXT_PUBLIC_SITE_URL="$WEB_BASE" \
    NODE_OPTIONS="--require $ROOT/scripts/sandbox-fs-guard.cjs" \
    "$NODE" server.js > /tmp/neostore-web.log 2>&1 &
  WEB_PID=$!
  disown
  cd "$ROOT"
  MODE="standalone server"
elif [[ -d "$STOREFRONT/.next" ]]; then
  cd "$STOREFRONT"
  API_BASE_URL="$API_BASE" NEXT_PUBLIC_API_BASE_URL="$API_BASE" \
    NEXT_PUBLIC_SITE_URL="$WEB_BASE" \
    NODE_OPTIONS="--require $ROOT/scripts/sandbox-fs-guard.cjs" \
    "$NODE" node_modules/next/dist/bin/next start -p "$WEB_PORT" \
    > /tmp/neostore-web.log 2>&1 &
  WEB_PID=$!
  disown
  cd "$ROOT"
  MODE="next start"
else
  MODE=""
fi

if [[ -n "$MODE" ]]; then
  echo "  mode: $MODE"
  if wait_for "$WEB_BASE/zh-CN" "the storefront" 60; then
    pass "storefront is serving"

    HOME_HTML="$("${CURL[@]}" "$WEB_BASE/zh-CN")"
    printf '%s' "$HOME_HTML" | grep -q "$ZH_NAME" \
      && pass "homepage lists the seeded product in Chinese" \
      || fail "homepage did not render '$ZH_NAME'"

    printf '%s' "$HOME_HTML" | grep -q '<html lang="zh-CN"' \
      && pass 'document declares lang="zh-CN"' \
      || fail "document did not declare the locale"

    for path in /en /ja /zh-CN/products "/zh-CN/products/$SLUG"; do
      expect_http "GET $path" "$WEB_BASE$path" 200
    done

    DETAIL_HTML="$("${CURL[@]}" "$WEB_BASE/zh-CN/products/$SLUG")"
    printf '%s' "$DETAIL_HTML" | grep -q 'application/ld+json' \
      && pass "product page ships JSON-LD" \
      || fail "product page is missing JSON-LD"

    # Next renders the attribute as hrefLang (HTML attributes are case-insensitive).
    printf '%s' "$DETAIL_HTML" | grep -qi 'hreflang' \
      && pass "product page ships hreflang alternates" \
      || fail "product page is missing hreflang alternates"

    "${CURL[@]}" "$WEB_BASE/sitemap.xml" | grep -q '<urlset' \
      && pass "sitemap.xml is served" \
      || fail "sitemap.xml is not a urlset"
  fi
fi

info "7. Admin console rendering"
ADMIN_INDEX="$ADMIN/dist/index.html"
if [[ "$SKIP_WEB" == "1" ]]; then
  echo "  skipped (--api-only)"
elif [[ -f "$ADMIN_INDEX" ]]; then
  cd "$ADMIN"
  VITE_API_TARGET="$API_BASE" \
    NODE_OPTIONS="--require $ROOT/scripts/sandbox-fs-guard.cjs" \
    "$NODE" node_modules/vite/bin/vite.js preview \
    --port "$ADMIN_PORT" --strictPort --host 127.0.0.1 \
    > /tmp/neostore-admin.log 2>&1 &
  ADMIN_PID=$!
  disown
  cd "$ROOT"

  if wait_for "$ADMIN_BASE/admin/" "the admin console" 40; then
    pass "admin console is serving"

    ADMIN_HTML="$("${CURL[@]}" "$ADMIN_BASE/admin/")"
    printf '%s' "$ADMIN_HTML" | grep -q '/admin/assets/' \
      && pass "index.html points at /admin/assets/" \
      || fail "index.html does not reference the /admin/ base path"

    # The shell is worthless if the bundle it names is a 404 — that mismatch is
    # exactly what a wrong `base` (or a stripping proxy) produces.
    ASSET="$(printf '%s' "$ADMIN_HTML" | grep -o '/admin/assets/[^"]*\.js' | head -1)"
    if [[ -n "$ASSET" ]]; then
      expect_http "GET $ASSET" "$ADMIN_BASE$ASSET" 200
    else
      fail "no JS bundle referenced from the admin shell"
    fi

    expect_http "GET /admin/assets/*.css" \
      "$ADMIN_BASE$(printf '%s' "$ADMIN_HTML" | grep -o '/admin/assets/[^"]*\.css' | head -1)" 200

    # Deep links have to reach the client router, not a 404 page.
    for path in /admin/orders /admin/products /admin/inventory /admin/settings; do
      expect_http "GET $path (SPA fallback)" "$ADMIN_BASE$path" 200
    done
  fi
else
  echo "  skipped (admin has not been built — run: cd admin && npm run build)"
fi

info "Result"
if [[ "$FAILURES" == "0" ]]; then
  printf '  \033[32mall checks passed\033[0m\n'
  exit 0
fi
printf '  \033[31m%s check(s) failed\033[0m\n' "$FAILURES"
exit 1
