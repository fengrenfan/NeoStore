/**
 * Drives the built storefront in a real browser.
 *
 * `next build` succeeding says nothing about whether the running site works.
 * This walks the buyer's path — land, browse, open a product, add it to the
 * cart, read the cart, reach checkout, switch language — and fails on any
 * console error, failed request, or cross-origin request.
 *
 *   node scripts/storefront-check.cjs <base-url> [locale]
 *
 * The cross-origin check is the one that earns its keep. The production image
 * is built with an empty `NEXT_PUBLIC_API_BASE_URL` so the browser calls
 * `/api/v1/...` on whatever origin served the page; if that inlining ever
 * regresses, this is what notices — the page would still render, it would just
 * quietly talk to the wrong host.
 */

const fs = require("fs");
const os = require("os");
const path = require("path");

function loadPlaywright() {
  const candidates = [
    process.env.PLAYWRIGHT_MODULE,
    "playwright",
    "playwright-core",
    "/Users/fengrenfan/node_modules/playwright",
  ].filter(Boolean);

  const failures = [];
  for (const candidate of candidates) {
    try {
      return require(candidate);
    } catch (error) {
      failures.push(`${candidate} (${error.code ?? error.message})`);
    }
  }
  throw new Error(
    `could not load playwright — tried ${failures.join(", ")}. Set PLAYWRIGHT_MODULE.`,
  );
}

const { chromium } = loadPlaywright();

const SHOTS = process.env.SHOT_DIR ?? "/tmp/neostore-storefront-shots";
const base = (process.argv[2] ?? "http://127.0.0.1:3000").replace(/\/$/, "");
const locale = process.argv[3] ?? "zh-CN";

/**
 * Find a Chromium Playwright can actually launch.
 *
 * Playwright insists on the exact revision it was built against, so a machine
 * with a slightly older download in its cache fails with "Executable doesn't
 * exist" even though a perfectly good browser is sitting right there.
 */
function findCachedChromium() {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;

  const roots = [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    path.join(os.homedir(), "Library/Caches/ms-playwright"),
    path.join(os.homedir(), ".cache/ms-playwright"),
  ].filter(Boolean);

  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const entry of fs.readdirSync(root).sort().reverse()) {
      if (!entry.startsWith("chromium-")) continue;
      const candidates = [
        "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-mac-x64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
        "chrome-linux64/chrome",
        "chrome-linux/chrome",
      ].map((relative) => path.join(root, entry, relative));
      const found = candidates.find((candidate) => fs.existsSync(candidate));
      if (found) return found;
    }
  }
  return null;
}

async function launchBrowser() {
  const cached = findCachedChromium();
  const attempts = [];
  if (cached) attempts.push({ executablePath: cached, headless: true });
  attempts.push({ headless: true });

  const failures = [];
  for (const options of attempts) {
    try {
      return await chromium.launch(options);
    } catch (error) {
      failures.push(error.message.split("\n")[0]);
    }
  }
  throw new Error(
    `could not launch chromium: ${failures.join(" | ")}. ` +
      "Run `npx playwright install chromium` or set CHROMIUM_PATH.",
  );
}

const problems = [];
let checks = 0;

function ok(label) {
  checks += 1;
  console.log(`  PASS  ${label}`);
}

function fail(label, detail) {
  problems.push(`${label}${detail ? ` — ${detail}` : ""}`);
  console.log(`  FAIL  ${label}${detail ? ` — ${detail}` : ""}`);
}

function expect(condition, label, detail) {
  if (condition) ok(label);
  else fail(label, detail);
}

/** Polls instead of racing: client-rendered panels arrive after hydration. */
async function waitFor(page, predicate, { timeout = 15000, step = 250 } = {}) {
  const deadline = Date.now() + timeout;
  for (;;) {
    try {
      if (await predicate()) return true;
    } catch {
      /* keep polling */
    }
    if (Date.now() > deadline) return false;
    await page.waitForTimeout(step);
  }
}

async function visibleText(page, text) {
  return (await page.locator(`text=${text}`).count()) > 0;
}

async function main() {
  fs.mkdirSync(SHOTS, { recursive: true });

  const browser = await launchBrowser();
  const context = await browser.newContext({
    viewport: { width: 1360, height: 900 },
    locale: "zh-CN",
  });
  const page = await context.newPage();

  const consoleErrors = [];
  const pageErrors = [];
  const failedRequests = [];
  const badResponses = [];
  const foreignOrigins = new Set();
  let origin = null;

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));
  page.on("requestfailed", (request) => {
    const url = request.url();
    const reason = request.failure()?.errorText ?? "";
    // Next prefetches RSC payloads and cancels the in-flight ones as the page
    // moves on. An aborted prefetch is the mechanism working, not a failure.
    if (reason.includes("ERR_ABORTED") && url.includes("_rsc=")) return;
    failedRequests.push(`${request.method()} ${url} (${reason})`);
  });
  page.on("response", (response) => {
    if (response.status() >= 400) {
      badResponses.push(`${response.status()} ${response.url()}`);
    }
  });
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.protocol === "data:" || url.protocol === "blob:") return;
    if (!origin) return;
    // Only API calls must be same-origin. The production bundle inlines an
    // empty `NEXT_PUBLIC_API_BASE_URL` precisely so they resolve against
    // whichever origin served the page; product images legitimately live on
    // the operator's CDN, and the seeded placeholder host is expected to miss.
    if (!url.pathname.startsWith("/api/")) return;
    if (url.origin !== origin) foreignOrigins.add(url.origin);
  });

  // ---------------------------------------------------------------- landing
  await page.goto(`${base}/`, { waitUntil: "domcontentloaded", timeout: 45000 });
  origin = new URL(page.url()).origin;

  const landedInLocale = await waitFor(page, async () =>
    new RegExp(`/${locale}(/|$)`).test(page.url()),
  );
  expect(landedInLocale, `"/" redirects into a locale`, `stuck at ${page.url()}`);

  const heroShown = await waitFor(page, () => visibleText(page, "把好设计寄到全世界"));
  expect(heroShown, "the hero renders (SSR copy present)");
  await page.screenshot({ path: `${SHOTS}/01-home.png`, fullPage: false });

  const productLinks = await page.locator(`a[href*="/products/"]`).count();
  expect(productLinks > 0, "the catalog renders product links", `found ${productLinks}`);
  if (productLinks === 0) {
    await browser.close();
    throw new Error("no products on the landing page — nothing further can be checked");
  }

  // ---------------------------------------------------------------- product
  await page.locator(`a[href*="/products/"]`).first().click();
  await page.waitForURL(/\/products\//, { timeout: 30000 });
  await page.waitForLoadState("domcontentloaded");

  const addButton = page.getByRole("button", { name: /加入购物车|已售罄|正在加入/ }).first();
  const hasAddButton = await waitFor(page, async () => (await addButton.count()) > 0);
  expect(hasAddButton, "the product page renders an add-to-cart control");
  expect(
    await visibleText(page, "商品详情"),
    "the product page renders the detail section",
  );
  await page.screenshot({ path: `${SHOTS}/02-product.png`, fullPage: false });

  // ------------------------------------------------------------------- cart
  if (hasAddButton) {
    const soldOut = /已售罄/.test((await addButton.innerText()) ?? "");
    if (soldOut) {
      fail("add to cart", "the default variant is sold out in the seed data");
    } else {
      await addButton.click();
      const added = await waitFor(page, async () => visibleText(page, "已加入购物车"));
      expect(added, "adding a variant succeeds (client-side POST to /api/v1)");
    }
  }

  await page.goto(`${base}/${locale}/cart`, { waitUntil: "domcontentloaded" });
  const cartRendered = await waitFor(page, async () => visibleText(page, "购物车"));
  expect(cartRendered, "the cart page renders");

  const cartHasLine = await waitFor(page, async () => {
    const text = (await page.locator("body").innerText()) ?? "";
    return /应付合计|购物车还是空的/.test(text);
  });
  expect(cartHasLine, "the cart resolves to a line item or an explicit empty state");
  await page.screenshot({ path: `${SHOTS}/03-cart.png`, fullPage: false });

  // --------------------------------------------------------------- checkout
  await page.goto(`${base}/${locale}/checkout`, { waitUntil: "domcontentloaded" });
  const checkoutRendered = await waitFor(page, async () => visibleText(page, "填写收货信息"));
  expect(checkoutRendered, "the checkout page renders its form");
  await page.screenshot({ path: `${SHOTS}/04-checkout.png`, fullPage: false });

  // ------------------------------------------------------------ i18n route
  await page.goto(`${base}/en`, { waitUntil: "domcontentloaded" });
  const englishHero = await waitFor(page, () =>
    visibleText(page, "Good design, shipped anywhere"),
  );
  expect(englishHero, "the /en locale renders its own copy");

  // ------------------------------------------------------------ free of noise
  expect(
    consoleErrors.length === 0,
    "no console errors",
    consoleErrors.slice(0, 3).join(" | "),
  );
  expect(pageErrors.length === 0, "no uncaught page errors", pageErrors.slice(0, 3).join(" | "));
  expect(
    failedRequests.length === 0,
    "no failed requests",
    failedRequests.slice(0, 3).join(" | "),
  );
  expect(
    badResponses.length === 0,
    "no 4xx/5xx responses",
    badResponses.slice(0, 3).join(" | "),
  );
  expect(
    foreignOrigins.size === 0,
    "every API request stays on the serving origin",
    `also called ${[...foreignOrigins].join(", ")}`,
  );

  await browser.close();

  console.log(
    `\n${checks}/${checks + problems.length} checks passed · screenshots in ${SHOTS}`,
  );
  if (problems.length) {
    console.log(`\n${problems.length} problem(s):`);
    for (const problem of problems) console.log(`  - ${problem}`);
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(`\nfatal: ${error.message}`);
  process.exitCode = 1;
});
