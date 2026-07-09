import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--version-dir") {
      out.versionDir = argv[++i];
    }
  }
  if (!out.versionDir) {
    throw new Error("missing --version-dir");
  }
  return out;
}

async function renderOne(browser, item) {
  fs.mkdirSync(path.dirname(item.image), { recursive: true });
  const page = await browser.newPage({
    viewport: { width: item.page_width, height: item.page_height },
    deviceScaleFactor: 1,
  });
  try {
    await page.goto(pathToFileURL(path.resolve(item.html)).href, { waitUntil: "load" });
    await page.evaluate(() => document.fonts && document.fonts.ready);
    await page.locator(".page").screenshot({ path: item.image });
  } finally {
    await page.close();
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const manifestPath = path.join(args.versionDir, "metadata", "html_manifest.json");
  const manifest = readJson(manifestPath);
  const chromePath = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const launchOptions = fs.existsSync(chromePath)
    ? { headless: true, executablePath: chromePath }
    : { headless: true };
  const browser = await chromium.launch(launchOptions);
  try {
    for (const item of manifest) {
      await renderOne(browser, item);
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ versionDir: args.versionDir, rendered: manifest.length }, null, 2));
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
