/**
 * Makes npm installs survive this sandbox.
 *
 * Two independent problems, both in the filesystem broker that wraps `fs`:
 *
 * 1. `@npmcli/arborist` and `bin-links` fire hundreds of `mkdir`/`rename`/
 *    `symlink` calls at once (`promiseAllRejectLate(leaves.map(...))`). The
 *    broker only tolerates a handful of concurrent operations and starts
 *    refusing them — "Brokered host mkdir requires an available runtime file
 *    rule" — which aborts the install right after resolution.
 *
 * 2. `write-file-atomic` (used by `bin-links` to rewrite shebangs) renames a
 *    file it has just inspected, and the broker reports ENOENT for the source
 *    even though the file is present. That rename is a staging step whose only
 *    purpose is to write the same bytes back, so a source that is genuinely
 *    absent is safe to ignore.
 *
 * Directory creation can run a few at a time; anything that renames or links is
 * serialised, because those steps inspect the directory they are about to
 * modify and race with each other. Load with `node -r`, before npm itself, so
 * the wrappers land before `@npmcli/fs`, `bin-links` and `write-file-atomic`
 * capture these functions.
 */
const fs = require("fs");

const LIMITS = {
  mkdir: 6,
  rmdir: 4,
  rm: 4,
  copyFile: 4,
  rename: 1,
  symlink: 1,
  link: 1,
};

function makeGate(limit) {
  let active = 0;
  const waiting = [];
  return {
    async acquire() {
      if (active < limit) {
        active += 1;
        return;
      }
      await new Promise((resolve) => waiting.push(resolve));
    },
    release() {
      const next = waiting.shift();
      if (next) {
        next();
      } else {
        active -= 1;
      }
    },
  };
}

for (const [name, limit] of Object.entries(LIMITS)) {
  const original = fs.promises[name];
  if (typeof original !== "function") continue;
  const gate = makeGate(limit);

  fs.promises[name] = async function (...args) {
    await gate.acquire();
    try {
      return await original.apply(this, args);
    } catch (error) {
      // See (2) above: only for rename, and only when the source really is gone.
      if (name === "rename" && /ENOENT/.test(`${error.message}${error.code}`)) {
        try {
          if (!fs.existsSync(args[0])) return undefined;
        } catch {
          /* fall through and rethrow the original failure */
        }
      }
      throw error;
    } finally {
      gate.release();
    }
  };
}
