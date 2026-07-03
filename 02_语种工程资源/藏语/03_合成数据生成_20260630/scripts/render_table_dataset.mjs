import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(payload, null, 2), "utf8");
}

function nowIso() {
  return new Date().toISOString();
}

function uuidish(input) {
  let h = 2166136261;
  for (let i = 0; i < input.length; i++) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  const hex = (h >>> 0).toString(16).padStart(8, "0");
  return `${hex.slice(0, 8)}-${hex.slice(0, 4)}-${hex.slice(4, 8)}-${hex.slice(0, 4)}-${hex}${hex.slice(0, 4)}`;
}

function parseArgs(argv) {
  const args = {};
  for (let i = 2; i < argv.length; i++) {
    const key = argv[i];
    if (!key.startsWith("--")) continue;
    const next = argv[i + 1];
    if (!next || next.startsWith("--")) {
      args[key.slice(2)] = true;
    } else {
      args[key.slice(2)] = next;
      i += 1;
    }
  }
  return args;
}

function loadLanguageProfile(profilePath) {
  if (!profilePath) {
    return {
      language_code: "mn",
      language_name: "蒙古语",
      script_note: "西里尔蒙古文",
    };
  }
  return readJson(profilePath);
}

async function collectBlocks(page) {
  return await page.evaluate(() => {
    const pageEl = document.querySelector(".page");
    const pageRect = pageEl.getBoundingClientRect();
    const elements = Array.from(document.querySelectorAll("[data-block-id]"));
    return elements.map((el, index) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const label = el.getAttribute("data-label") || "text";
      const text = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
      const xMin = rect.left - pageRect.left;
      const yMin = rect.top - pageRect.top;
      const xMax = rect.right - pageRect.left;
      const yMax = rect.bottom - pageRect.top;
      return {
        block_id: el.getAttribute("data-block-id"),
        coordinates: {
          x_min: Number(xMin.toFixed(1)),
          y_min: Number(yMin.toFixed(1)),
          x_max: Number(xMax.toFixed(1)),
          y_max: Number(yMax.toFixed(1)),
        },
        points: null,
        block_label: label,
        block_content: text,
        order: String(index),
        attributes: {
          tag: el.tagName.toLowerCase(),
          row: el.getAttribute("data-row"),
          col: el.getAttribute("data-col"),
          font_size: style.fontSize,
          font_family: style.fontFamily,
        },
      };
    });
  });
}

function cropBlocks(blocks, crop) {
  const shifted = [];
  for (const block of blocks) {
    const c = block.coordinates;
    const xMin = Math.max(0, c.x_min - crop.x);
    const yMin = Math.max(0, c.y_min - crop.y);
    const xMax = Math.min(crop.width, c.x_max - crop.x);
    const yMax = Math.min(crop.height, c.y_max - crop.y);
    if (xMax - xMin < 1 || yMax - yMin < 1) {
      continue;
    }
    shifted.push({
      ...block,
      coordinates: {
        x_min: Number(xMin.toFixed(1)),
        y_min: Number(yMin.toFixed(1)),
        x_max: Number(xMax.toFixed(1)),
        y_max: Number(yMax.toFixed(1)),
      },
    });
  }
  return shifted;
}

async function computeAutoCrop(page, blocks, args, manifestItem = {}) {
  const enabled = args["auto-crop"] === true || args["auto-crop"] === "true" || args["auto-crop"] === "1";
  const preserveFullPage =
    manifestItem.preserve_full_page === true ||
    args["preserve-full-page"] === true ||
    args["preserve-full-page"] === "true" ||
    args["preserve-full-page"] === "1";
  const pageBox = await page.evaluate(() => {
    const pageEl = document.querySelector(".page");
    const pageRect = pageEl.getBoundingClientRect();
    const rects = [];
    for (const el of Array.from(pageEl.children)) {
      const label = el.getAttribute("data-label");
      if (label === "footer" || label === "page_number" || el.classList.contains("footer") || el.classList.contains("page-no")) {
        continue;
      }
      const rect = el.getBoundingClientRect();
      if (rect.width < 2 || rect.height < 2) {
        continue;
      }
      rects.push({
        x_min: rect.left - pageRect.left,
        y_min: rect.top - pageRect.top,
        x_max: rect.right - pageRect.left,
        y_max: rect.bottom - pageRect.top,
      });
    }
    return {
      width: Math.round(pageRect.width),
      height: Math.round(pageRect.height),
      structural_rects: rects,
    };
  });

  if (!enabled) {
    return { x: 0, y: 0, width: pageBox.width, height: pageBox.height, enabled: false };
  }
  if (preserveFullPage) {
    return { x: 0, y: 0, width: pageBox.width, height: pageBox.height, enabled: true, preserved_full_page: true };
  }

  const rects = [...pageBox.structural_rects];
  for (const block of blocks) {
    if (block.block_label === "footer" || block.block_label === "page_number") {
      continue;
    }
    const c = block.coordinates;
    if (c.x_max - c.x_min < 2 || c.y_max - c.y_min < 2) {
      continue;
    }
    rects.push(c);
  }
  if (!rects.length) {
    return { x: 0, y: 0, width: pageBox.width, height: pageBox.height, enabled: false };
  }

  const content = {
    x_min: Math.min(...rects.map((r) => r.x_min)),
    y_min: Math.min(...rects.map((r) => r.y_min)),
    x_max: Math.max(...rects.map((r) => r.x_max)),
    y_max: Math.max(...rects.map((r) => r.y_max)),
  };
  const explicitPadding = Number.parseInt(args["crop-padding"] || "", 10);
  const dynamicPadding = Math.round(Math.min(pageBox.width, pageBox.height) * 0.035);
  const padding = Number.isFinite(explicitPadding) ? explicitPadding : Math.max(36, dynamicPadding);
  let x = Math.max(0, Math.floor(content.x_min - padding));
  let y = Math.max(0, Math.floor(content.y_min - padding));
  let xMax = Math.min(pageBox.width, Math.ceil(content.x_max + padding));
  let yMax = Math.min(pageBox.height, Math.ceil(content.y_max + padding));

  if (xMax - x > pageBox.width * 0.86) {
    x = 0;
    xMax = pageBox.width;
  }
  if (yMax - y > pageBox.height * 0.94) {
    y = 0;
    yMax = pageBox.height;
  }

  const minWidth = Math.min(pageBox.width, 420);
  const minHeight = Math.min(pageBox.height, 420);
  if (xMax - x < minWidth) {
    const delta = minWidth - (xMax - x);
    x = Math.max(0, x - Math.floor(delta / 2));
    xMax = Math.min(pageBox.width, x + minWidth);
    x = Math.max(0, xMax - minWidth);
  }
  if (yMax - y < minHeight) {
    const delta = minHeight - (yMax - y);
    y = Math.max(0, y - Math.floor(delta / 2));
    yMax = Math.min(pageBox.height, y + minHeight);
    y = Math.max(0, yMax - minHeight);
  }

  return {
    x,
    y,
    width: Math.max(1, xMax - x),
    height: Math.max(1, yMax - y),
    enabled: true,
    original_width: pageBox.width,
    original_height: pageBox.height,
    content_bbox: content,
    padding,
  };
}

async function pageDiagnostics(page) {
  return await page.evaluate(() => {
    const pageEl = document.querySelector(".page");
    const pageRect = pageEl.getBoundingClientRect();
    const marked = Array.from(document.querySelectorAll("[data-block-id]"));
    const overflowBlocks = [];
    for (const el of marked) {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const clippedByStyle =
        style.overflow === "hidden" ||
        style.overflowX === "hidden" ||
        style.overflowY === "hidden" ||
        style.textOverflow === "ellipsis";
      const outsidePage =
        rect.left < pageRect.left - 1 ||
        rect.top < pageRect.top - 1 ||
        rect.right > pageRect.right + 1 ||
        rect.bottom > pageRect.bottom + 1;
      const hiddenOverflow =
        clippedByStyle &&
        (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2);
      const overflow = outsidePage || hiddenOverflow;
      if (overflow) {
        overflowBlocks.push({
          block_id: el.getAttribute("data-block-id"),
          label: el.getAttribute("data-label"),
          text: (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 80),
          clientWidth: el.clientWidth,
          scrollWidth: el.scrollWidth,
          clientHeight: el.clientHeight,
          scrollHeight: el.scrollHeight,
        });
      }
    }
    return {
      marked_blocks: marked.length,
      page_width: Math.round(pageRect.width),
      page_height: Math.round(pageRect.height),
      body_scroll_width: document.body.scrollWidth,
      body_scroll_height: document.body.scrollHeight,
      overflow_blocks: overflowBlocks,
    };
  });
}

async function renderOne(browser, htmlPath, outDir, manifestItem, languageProfile, args) {
  const page = await browser.newPage({
    viewport: {
      width: manifestItem.page_width || 1240,
      height: manifestItem.page_height || 1754,
      deviceScaleFactor: 1,
    },
  });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
  await page.emulateMedia({ media: "screen" });
  const pageHeight = await page.evaluate(() => Math.ceil(document.querySelector(".page").getBoundingClientRect().height));
  await page.setViewportSize({ width: manifestItem.page_width || 1240, height: pageHeight });

  const rawBlocks = await collectBlocks(page);
  const crop = await computeAutoCrop(page, rawBlocks, args, manifestItem);
  const diagnostics = await pageDiagnostics(page);
  const blocks = crop.enabled ? cropBlocks(rawBlocks, crop) : rawBlocks;

  const imageFile = `${manifestItem.document_id}.png`;
  const imagePath = path.join(outDir, "images", imageFile);
  fs.mkdirSync(path.dirname(imagePath), { recursive: true });
  if (crop.enabled) {
    await page.screenshot({
      path: imagePath,
      clip: { x: crop.x, y: crop.y, width: crop.width, height: crop.height },
    });
  } else {
    await page.locator(".page").screenshot({ path: imagePath });
  }
  await page.close();

  const label = {
    image_id: uuidish(manifestItem.document_id),
    file_name: imageFile,
    status: "synthetic",
    attributes: {
      generator: manifestItem.generator || "html_layout_synthetic_generator",
      language_code: languageProfile.language_code || "mn",
      language_name: languageProfile.language_name || "蒙古语",
      script_note: languageProfile.script_note || "西里尔蒙古文",
      template_type: manifestItem.template_type || manifestItem.category || "table_document",
      category: manifestItem.category || null,
      variant: manifestItem.variant || null,
      layout_name: manifestItem.layout_name || null,
      document_id: manifestItem.document_id,
      title: manifestItem.title,
      doc_no: manifestItem.doc_no,
      date: manifestItem.date,
      rows: manifestItem.rows,
      columns: manifestItem.columns,
      source_records: manifestItem.source_records,
      diagnostics: {
        ...diagnostics,
        crop,
      },
    },
    blocks,
    created_at: nowIso(),
    updated_at: nowIso(),
  };
  const labelPath = path.join(outDir, "labels", `${manifestItem.document_id}.json`);
  writeJson(labelPath, label);
  return {
    document_id: manifestItem.document_id,
    category: manifestItem.category || null,
    variant: manifestItem.variant || null,
    layout_name: manifestItem.layout_name || null,
    image: imagePath,
    label: labelPath,
    html: htmlPath,
    blocks: blocks.length,
    overflow_blocks: diagnostics.overflow_blocks.length,
    page_width: crop.enabled ? crop.width : diagnostics.page_width,
    page_height: crop.enabled ? crop.height : diagnostics.page_height,
  };
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args["input-dir"]) {
    throw new Error("--input-dir is required");
  }
  const outDir = args["input-dir"];
  const languageProfile = loadLanguageProfile(args["language-profile"]);
  const manifestPath = path.join(outDir, "metadata", "html_manifest.json");
  const manifest = readJson(manifestPath);
  const systemChrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
  const launchOptions = fs.existsSync(systemChrome)
    ? { headless: true, executablePath: systemChrome }
    : { headless: true };
  const browser = await chromium.launch(launchOptions);
  const results = [];
  try {
    for (const item of manifest) {
      const htmlPath = path.join(outDir, "html", `${item.document_id}.html`);
      results.push(await renderOne(browser, htmlPath, outDir, item, languageProfile, args));
      console.log(`rendered ${item.document_id}`);
    }
  } finally {
    await browser.close();
  }
  writeJson(path.join(outDir, "metadata", "render_manifest.json"), results);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
