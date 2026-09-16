/**
 * Repro for "buyer-side currency switch has no effect".
 * Switches the region <select> and reports whether the displayed price
 * currency changes, plus the actual product-fetch URL the browser issued.
 */
const fs = require("fs");
const os = require("os");
const path = require("path");

function loadPlaywright() {
  for (const c of ["playwright", "playwright-core", "/Users/fengrenfan/node_modules/playwright"]) {
    try { return require(c); } catch {}
  }
  throw new Error("playwright not found");
}
const { chromium } = loadPlaywright();

function findChromium() {
  const roots = [process.env.PLAYWRIGHT_BROWSERS_PATH, path.join(os.homedir(), "Library/Caches/ms-playwright"), path.join(os.homedir(), ".cache/ms-playwright")].filter(Boolean);
  for (const root of roots) {
    if (!fs.existsSync(root)) continue;
    for (const entry of fs.readdirSync(root).sort().reverse()) {
      if (!entry.startsWith("chromium-")) continue;
      const cand = path.join(root, entry, "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing");
      if (fs.existsSync(cand)) return cand;
    }
  }
  return null;
}

const base = (process.argv[2] ?? "https://store.xiaodigua.shop").replace(/\/$/, "");

async function main() {
  const browser = await chromium.launch({ executablePath: findChromium() || undefined, headless: true });
  const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });

  const productUrls = [];
  page.on("request", (req) => {
    const u = req.url();
    if (u.includes("/api/v1/store/products")) productUrls.push(u);
  });

  await page.goto(`${base}/zh-CN`, { waitUntil: "domcontentloaded", timeout: 45000 });
  await page.waitForTimeout(1500);

  const firstPrice = async () =>
    (await page.locator("a[href*='/products/'] p.text-neon-cyan").first().innerText().catch(() => "")) ||
    (await page.locator(".text-neon-cyan").first().innerText().catch(() => ""));

  const before = await firstPrice();
  console.log("BEFORE switch  :", JSON.stringify(before));
  console.log("region cookie :", await page.evaluate(() => document.cookie));

  // Inspect the select
  const select = page.locator('select[aria-label="Region"]');
  const opts = await select.locator("option").allInnerTexts();
  const vals = await select.locator("option").evaluateAll((els) => els.map((e) => e.value));
  console.log("select options:", JSON.stringify(opts));
  console.log("select values :", JSON.stringify(vals));
  console.log("select value  :", await select.inputValue());

  // Switch to the CN (中国) option
  const cnIdx = vals.indexOf("cn");
  if (cnIdx >= 0) {
    await select.selectOption({ value: "cn" });
  } else {
    console.log("!! no 'cn' option found, trying first non-default");
    await select.selectOption({ index: 1 });
  }
  await page.waitForTimeout(2500);

  const after = await firstPrice();
  console.log("AFTER  switch  :", JSON.stringify(after));
  console.log("region cookie :", await page.evaluate(() => document.cookie));
  console.log("select value  :", await select.inputValue());

  console.log("product fetch URLs seen:");
  for (const u of productUrls) console.log("  ", u);

  console.log(before !== after ? "\nRESULT: currency DID change" : "\nRESULT: currency did NOT change (bug confirmed)");
  await browser.close();
}
main().catch((e) => { console.error("fatal:", e.message); process.exit(1); });
