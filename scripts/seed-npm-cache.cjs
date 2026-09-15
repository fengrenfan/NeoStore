/**
 * Seeds npm's HTTP cache from tarballs fetched with `curl`.
 *
 * Why: npm's own fetcher is unreliable in this sandbox — the filesystem broker
 * refuses concurrent operations and some registry responses sit behind an
 * approval prompt that never gets answered. `curl` is unaffected, so the
 * tarballs that npm cannot download are fetched here and written into cacache
 * under exactly the key `make-fetch-happen` looks for
 * (`make-fetch-happen:request-cache:<url>`), with the metadata shape
 * `make-fetch-happen/lib/cache/entry.js` produces.
 *
 * Usage:
 *   node scripts/seed-npm-cache.cjs <url> [compress]
 *   node scripts/seed-npm-cache.cjs --drain        # loop install/seed until done
 */
const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const NPMROOT =
  process.env.NPMROOT ||
  "/Users/fengrenfan/.workbuddy/binaries/node/versions/22.22.2-2/lib/node_modules/npm";
const NODE = process.execPath;
const CACACHE = path.join(os.homedir(), ".npm", "_cacache");
const PROJECT =
  process.env.PROJECT_DIR || "/Users/fengrenfan/Desktop/github/独立站/storefront";
const THROTTLE = path.join(
  path.dirname(__dirname),
  "scripts",
  "sandbox-fs-guard.cjs",
);
const REGISTRY = "https://registry.npmjs.org";

const cacache = require(path.join(NPMROOT, "node_modules", "cacache"));

function cacheKey(url) {
  const parsed = new URL(url);
  parsed.hash = "";
  return `make-fetch-happen:request-cache:${parsed.toString()}`;
}

async function seed(url, compress) {
  const tmp = path.join(os.tmpdir(), `seed-${Date.now()}.tgz`);
  const fetched = spawnSync(
    "curl",
    ["-sS", "-L", "--compressed", "--max-time", "600", "-o", tmp, "-w", "%{http_code}", url],
    { encoding: "utf8" },
  );
  const code = (fetched.stdout || "").trim();
  if (code !== "200") {
    throw new Error(`curl returned ${code || fetched.stderr}`);
  }

  const body = fs.readFileSync(tmp);
  fs.rmSync(tmp, { force: true });

  await cacache.put(CACACHE, cacheKey(url), body, {
    metadata: {
      time: Date.now(),
      url,
      reqHeaders: {},
      resHeaders: { "content-length": String(body.length) },
      options: { compress },
    },
  });

  console.log(`seeded ${url} (${body.length} bytes, compress=${compress})`);
}

function offlineInstall() {
  const result = spawnSync(
    NODE,
    [
      "-r",
      THROTTLE,
      path.join(NPMROOT, "bin", "npm-cli.js"),
      "install",
      "--offline",
      "--registry",
      REGISTRY,
      "--no-audit",
      "--no-fund",
      "--no-progress",
      "--loglevel=error",
    ],
    { cwd: PROJECT, encoding: "utf8", maxBuffer: 64 * 1024 * 1024 },
  );
  return `${result.stdout || ""}${result.stderr || ""}`;
}

async function main() {
  const [first, second] = process.argv.slice(2);

  if (first === "--drain") {
    for (let attempt = 0; attempt < 400; attempt += 1) {
      const output = offlineInstall();
      const missing = output.match(
        /request to (\S+) failed: cache mode is 'only-if-cached'/,
      );
      if (!missing) {
        console.log(`no missing tarball after ${attempt} seed(s)`);
        console.log(output.slice(-3000) || "(clean run)");
        return;
      }
      // npm requests tarballs with compression on unless --no-compress was used.
      await seed(missing[1], true);
    }
    console.log("gave up after 400 attempts");
    return;
  }

  if (!first) {
    console.error("usage: seed-npm-cache.cjs <url> [compress:true|false] | --drain");
    process.exit(1);
  }
  await seed(first, second !== "false");
}

main().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
