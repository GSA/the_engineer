// Playwright driver for scripts/demo-capture.py. Reads one JSON job file and
// prints one JSON result line. Only loopback requests reach the network.
import { createRequire } from "node:module";
import { readFileSync, renameSync } from "node:fs";
import { join } from "node:path";

const job = JSON.parse(readFileSync(process.argv[2], "utf8"));
const require = createRequire(import.meta.url);
const { chromium } = require(job.playwright_core);

const LOOPBACK = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);
function allowed(url) {
    if (url.startsWith("data:") || url.startsWith("blob:") || url === "about:blank") return true;
    try {
        const parsed = new URL(url);
        if (!["http:", "https:", "ws:", "wss:"].includes(parsed.protocol)) return false;
        return LOOPBACK.has(parsed.hostname) || /^127\.\d+\.\d+\.\d+$/.test(parsed.hostname);
    } catch {
        return false;
    }
}

const [width, height] = job.viewport;
const artifacts = [];
let blocked = 0;
const browser = await chromium.launch({ headless: true });
try {
    const context = await browser.newContext({
        viewport: { width, height },
        deviceScaleFactor: 1,
        locale: "en-US",
        timezoneId: "UTC",
        colorScheme: "light",
        reducedMotion: "reduce",
        permissions: [],
        serviceWorkers: "block",
        acceptDownloads: false,
        ...(job.video ? { recordVideo: { dir: job.out_dir, size: { width, height } } } : {}),
    });
    context.setDefaultTimeout(job.step_timeout_ms);
    await context.route("**/*", (route) => {
        if (allowed(route.request().url())) return route.continue();
        blocked += 1;
        return route.abort("blockedbyclient");
    });
    const page = await context.newPage();
    const shot = async (name) => {
        const file = `${name}.png`;
        await page.screenshot({ path: join(job.out_dir, file), fullPage: job.full_page });
        artifacts.push({ kind: "screenshot", file });
    };
    await page.goto(job.url, { waitUntil: "load" });
    for (const step of job.steps) {
        if (job.video) await page.waitForTimeout(job.step_pause_ms);
        switch (step.action) {
            case "click": await page.click(step.selector); break;
            case "fill": await page.fill(step.selector, step.value); break;
            case "press": await page.press(step.selector, step.value); break;
            case "wait": await page.waitForTimeout(step.ms); break;
            case "waitfor": await page.waitForSelector(step.selector); break;
            case "goto": await page.goto(step.url, { waitUntil: "load" }); break;
            case "screenshot": await shot(step.name); break;
            default: throw new Error(`unsupported step ${step.action}`);
        }
    }
    if (job.video) await page.waitForTimeout(job.step_pause_ms);
    await shot("final");
    const video = page.video();
    await context.close();
    if (video) {
        const recorded = await video.path();
        renameSync(recorded, join(job.out_dir, "demo.webm"));
        artifacts.push({ kind: "video", file: "demo.webm" });
    }
} finally {
    await browser.close();
}
process.stdout.write(JSON.stringify({ artifacts, blocked_requests: blocked }) + "\n");
