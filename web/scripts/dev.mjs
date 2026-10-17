// Local dev shares my-hub/.env with the collector. Load it, then run the Next CLI in this same process
// (node --env-file fails because Next forwards execArgv via NODE_OPTIONS; same approach as RichRich/web).
import { existsSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { pathToFileURL } from "node:url";

const envFile = path.resolve(import.meta.dirname, "../../.env");
if (existsSync(envFile)) process.loadEnvFile(envFile);

const nextBin = createRequire(import.meta.url).resolve("next/dist/bin/next");
process.argv = [process.argv[0], nextBin, "dev", ...process.argv.slice(2)];
await import(pathToFileURL(nextBin).href);
