import { copyFileSync, mkdirSync, readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { join } from "node:path";
// Node's recursive cp exits unexpectedly on this Windows checkout; copy each asset explicitly.
function copyAssets(source, destination) {
  mkdirSync(destination, { recursive: true });
  for (const item of readdirSync(source, { withFileTypes: true })) {
    const from = join(source, item.name),
      to = join(destination, item.name);
    if (item.isDirectory()) copyAssets(from, to);
    else copyFileSync(from, to);
  }
}
copyAssets(".next/static", ".next/standalone/.next/static");
copyAssets("public", ".next/standalone/public");
const result = spawnSync(process.execPath, [".next/standalone/server.js"], {
  stdio: "inherit",
  env: { ...process.env, HOSTNAME: process.env.HOSTNAME || "127.0.0.1" },
});
process.exit(result.status ?? 1);
