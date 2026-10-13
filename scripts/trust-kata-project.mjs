import { readFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url)).replace(/\/$/, "");
const state = join(root, ".local/environment");
const config = JSON.parse(await readFile(join(state, "environment.json"), "utf8"));
const { ProjectTrustStore } = await import(
  pathToFileURL(join(dirname(config.pi_executable), "index.js")).href
);
const trust = new ProjectTrustStore(join(state, "pi"));
if (trust.get(root) === false) {
  throw new Error("Private Pi explicitly distrusts this project; resolve that decision before setup.");
}
trust.set(root, true);
console.log("Private Pi trusts this checkout's project resources; no global profile was changed.");
