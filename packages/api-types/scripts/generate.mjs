/**
 * Generate TypeScript types from the FastAPI OpenAPI schema.
 *
 * Usage:
 *   node scripts/generate.mjs                          # from running server
 *   node scripts/generate.mjs --from-file schema.json  # from exported file
 *
 * The script:
 *   1. Loads the OpenAPI spec (from server or file)
 *   2. Runs openapi-typescript to generate raw types
 *   3. Writes generated/openapi.d.ts (raw) + src/index.ts (re-exports)
 */

import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const GENERATED_DIR = resolve(ROOT, "generated");
const SCHEMA_FILE = resolve(GENERATED_DIR, "openapi.json");
const TYPES_FILE = resolve(GENERATED_DIR, "openapi.d.ts");

// Parse args
const args = process.argv.slice(2);
const fromFileIdx = args.indexOf("--from-file");
const fromFile = fromFileIdx >= 0 ? args[fromFileIdx + 1] : null;

async function fetchSchema() {
  if (fromFile) {
    console.log(`Reading schema from ${fromFile}`);
    return readFileSync(resolve(process.cwd(), fromFile), "utf-8");
  }

  // Try fetching from running server
  const url =
    process.env.API_URL || "http://localhost:8000/openapi.json";
  console.log(`Fetching schema from ${url}`);
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(
      `Failed to fetch OpenAPI schema from ${url} (${res.status}). ` +
        `Either start the server or use: node scripts/generate.mjs --from-file schema.json`,
    );
  }
  return await res.text();
}

async function main() {
  // Ensure output dir
  if (!existsSync(GENERATED_DIR)) {
    mkdirSync(GENERATED_DIR, { recursive: true });
  }

  // 1. Get the schema
  const schemaText = await fetchSchema();
  writeFileSync(SCHEMA_FILE, schemaText);
  console.log(`Schema saved to ${SCHEMA_FILE}`);

  // 2. Run openapi-typescript
  const npxBin = resolve(ROOT, "node_modules", ".bin", "openapi-typescript");
  const cmd = existsSync(npxBin)
    ? `${npxBin} ${SCHEMA_FILE} -o ${TYPES_FILE}`
    : `npx openapi-typescript ${SCHEMA_FILE} -o ${TYPES_FILE}`;

  console.log("Generating types...");
  execSync(cmd, { stdio: "inherit", cwd: ROOT });
  console.log(`Types written to ${TYPES_FILE}`);
}

main().catch((err) => {
  console.error(err.message);
  process.exit(1);
});
