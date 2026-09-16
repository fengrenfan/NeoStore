/**
 * Drives the built admin console in a real browser.
 *
 * "It compiles" is not "it works": this walks the actual flows an operator
 * uses — log in, read the dashboard, open every page, adjust stock, and drive
 * one order through the status machine — and fails on any console error,
 * failed request or missing assertion.
 *
 *   node scripts/admin-check.cjs <base-url> <order-number>
 *
 * Playwright is resolved from the usual places; point PLAYWRIGHT_MODULE at a
 * specific install if none of them fit. Set CHROMIUM_PATH to force a particular
 * browser binary, otherwise Playwright uses the one it manages.
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

const SHOTS = process.env.SHOT_DIR ?? "/tmp/neostore-admin-shots";

const base = (process.argv[2] ?? "http://127.0.0.1:5173/admin").replace(/\/$/, "");
const orderNumber = process.argv[3];

// Admin credentials come from the deployment's seeded values. The server
// backend/.env holds SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD; default to the
// documented dev fallback only when neither is supplied.
const adminEmail = process.env.ADMIN_EMAIL ?? "admin@neostore.local";
const adminPassword = process.env.ADMIN_PASSWORD ?? "admin123";

/**
 * Find a Chromium Playwright can actually launch.
 *
 * Playwright insists on the exact revision it was built against, so a machine
 * with a slightly older download in its cache fails with "Executable doesn't
 * exist" even though a perfectly good browser is sitting right there. Rather
 * than make everyone run `npx playwright install`, look in the cache too.
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
      // `chromium_headless_shell-*` is a different, stripped-down build.
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

function bad(label, detail) {
  checks += 1;
  console.log(`  FAIL  ${label}${detail ? ` — ${detail}` : ""}`);
  problems.push(label);
}

async function main() {
  fs.mkdirSync(SHOTS, { recursive: true });

  const browser = await launchBrowser();
  const page = await browser.newPage({ viewport: { width: 1440, height: 980 } });

  page.on("console", (message) => {
    if (message.type() === "error") problems.push(`console: ${message.text()}`);
  });
  page.on("pageerror", (error) => problems.push(`pageerror: ${error.message}`));
  page.on("requestfailed", (request) => {
    problems.push(`requestfailed: ${request.url()} ${request.failure()?.errorText ?? ""}`);
  });
  // A 404 the console swallows would otherwise only show up as a vague
  // "Failed to load resource" line with no URL attached.
  page.on("response", (response) => {
    if (response.status() >= 400) {
      problems.push(`http ${response.status()}: ${response.url()}`);
    }
  });

  const shot = async (name) => {
    await page.screenshot({ path: `${SHOTS}/${name}.png`, fullPage: true });
  };

  // ---------------------------------------------------------------- login
  await page.goto(`${base}/`, { waitUntil: "domcontentloaded" });
  await page.getByText("管理控制台").waitFor({ timeout: 15000 });
  ok("login screen renders");
  await shot("01-login");

  await page.fill('input[type="email"]', adminEmail);
  await page.fill('input[type="password"]', adminPassword);
  await page.click('button[type="submit"]');

  await page.getByRole("heading", { name: "概览", exact: true }).waitFor({ timeout: 15000 });
  ok("login succeeds and the dashboard takes over");

  // ------------------------------------------------------------ dashboard
  // The heading paints before React Query resolves, so poll for the numbers
  // rather than reading whatever is on screen at that instant.
  const readStats = async () =>
    (await page.locator(".surface p.text-2xl").allTextContents()).map((text) => text.trim());

  let stats = [];
  for (let attempt = 0; attempt < 40; attempt += 1) {
    stats = await readStats();
    if (stats[0] === "3" && Number(stats[1]) >= 1) break;
    await page.waitForTimeout(250);
  }

  if (stats[0] === "3") ok("dashboard counts the seeded catalogue (3 products)");
  else bad("dashboard product count", `got ${JSON.stringify(stats)}`);

  if (Number(stats[1]) >= 1) ok(`dashboard counts orders (${stats[1]})`);
  else bad("dashboard order count", `got ${JSON.stringify(stats)}`);

  await shot("02-dashboard");

  // The backend sends UTC with an offset; if the card were rendered from a
  // naive timestamp the hour would be eight off in CST. Compare against the
  // browser's own clock in the same zone.
  const shownHour = await page
    .locator("li", { hasText: "NS-" })
    .first()
    .locator("span")
    .first()
    .innerText()
    .catch(() => "");
  const localHour = String(new Date().getHours());
  if (shownHour.includes(`${localHour}:`)) {
    ok(`timestamps render in the browser's timezone (${shownHour.match(/\d+:\d+/)?.[0]})`);
  } else {
    bad("timestamp timezone", `card shows '${shownHour}', local hour is ${localHour}`);
  }

  // ------------------------------------------------------------- products
  await page.goto(`${base}/products`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "商品", exact: true }).waitFor({ timeout: 15000 });
  await page.getByText("霓虹 T 恤").first().waitFor({ timeout: 15000 });
  ok("products page lists the seeded product with its Chinese name");

  const variantToggle = page.getByRole("button", { name: "变体与定价" }).first();
  if (await variantToggle.count()) {
    await variantToggle.click();
    await page.getByText("NEON-TEE-S").first().waitFor({ timeout: 10000 });
    ok("expanding a product shows its variants and price fields");
  } else {
    bad("products page has no variant toggle");
  }
  await page.waitForTimeout(500);
  await shot("03-products");

  // ------------------------------------------------------------ inventory
  await page.goto(`${base}/inventory`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "库存", exact: true }).waitFor({ timeout: 15000 });
  await page.getByText("NEON-TEE-S").first().waitFor({ timeout: 15000 });
  ok("inventory page lists variants with their SKUs");

  // Adjust stock through the UI and confirm the number actually moves.
  const row = page.locator("tr", { hasText: "NEON-TEE-S" }).first();
  const availableBefore = Number(await row.locator("td").nth(4).innerText());
  await row.locator('input[type="number"]').fill("2");
  await row.getByRole("button", { name: "应用" }).click();
  await page.waitForTimeout(1500);
  const availableAfter = Number(await page.locator("tr", { hasText: "NEON-TEE-S" }).first().locator("td").nth(4).innerText());
  if (availableAfter === availableBefore + 2) {
    ok(`inventory adjustment applies through the UI (${availableBefore} → ${availableAfter})`);
  } else {
    bad("inventory adjustment", `${availableBefore} → ${availableAfter}`);
  }
  await shot("04-inventory");

  // ------------------------------------------------------------- settings
  await page.goto(`${base}/settings`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "设置", exact: true }).waitFor({ timeout: 15000 });
  await page.getByText("汇率（基准").first().waitFor({ timeout: 15000 });
  for (const label of ["语言", "币种", "地区"]) {
    if (await page.getByText(label, { exact: false }).first().count()) ok(`settings shows the ${label} table`);
    else bad(`settings is missing the ${label} table`);
  }
  // A cell, not the hidden <option> inside the base-currency <select>.
  await page.getByRole("cell", { name: "CNY", exact: true }).first().waitFor({ timeout: 10000 });
  ok("settings lists currencies from the API");
  await page.waitForTimeout(500);
  await shot("05-settings");

  // --------------------------------------------------------- order detail
  if (orderNumber) {
    await page.goto(`${base}/orders/${orderNumber}`, { waitUntil: "domcontentloaded" });
    await page.getByText(orderNumber).first().waitFor({ timeout: 15000 });
    ok(`order detail opens for ${orderNumber}`);

    const payButton = page.getByRole("button", { name: "已支付" });
    if (await payButton.count()) {
      await payButton.first().click();
      await page.getByText("已支付", { exact: true }).first().waitFor({ timeout: 15000 });
      await page.waitForTimeout(800);
      ok("transitioning the order to paid works from the console");
    } else {
      bad("order detail offered no paid transition");
    }
    await shot("06-order-detail");
  }

  await browser.close();
}

main()
  .then(() => {
    console.log("");
    if (problems.length === 0) {
      console.log(`all ${checks} browser checks passed`);
      process.exit(0);
    }
    console.log(`${problems.length} problem(s):`);
    for (const problem of problems) console.log(`  - ${problem}`);
    process.exit(1);
  })
  .catch((error) => {
    console.error("browser check crashed:", error.message);
    process.exit(1);
  });
