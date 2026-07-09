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

function attrDeep(el, name) {
  return el.getAttribute(name) || el.closest(`[${name}]`)?.getAttribute(name) || null;
}

function normalizeBool(value, defaultValue = true) {
  if (value === null || value === undefined || value === "") return defaultValue;
  return !["false", "0", "no", "off"].includes(String(value).toLowerCase());
}

async function collectBlocks(page) {
  return await page.evaluate(() => {
    function attrDeep(el, name) {
      return el.getAttribute(name) || el.closest(`[${name}]`)?.getAttribute(name) || null;
    }
    function normalizeBool(value, defaultValue = true) {
      if (value === null || value === undefined || value === "") return defaultValue;
      return !["false", "0", "no", "off"].includes(String(value).toLowerCase());
    }
    const pageEl = document.querySelector(".page");
    const pageRect = pageEl.getBoundingClientRect();
    const elements = Array.from(document.querySelectorAll("[data-block-id]"));
    return elements.map((el, index) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      const label = el.getAttribute("data-label") || "text";
      const text = (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
      const flowOrderable = normalizeBool(attrDeep(el, "data-ocr-orderable"), true);
      const isText = el.getAttribute("data-is-text") === "false" || !flowOrderable ? false : true;
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
        is_text: isText,
        order: String(index),
        attributes: {
          tag: el.tagName.toLowerCase(),
          row: el.getAttribute("data-row"),
          col: el.getAttribute("data-col"),
          dom_index: index,
          reading_flow_id: el.getAttribute("data-reading-flow-id") || el.closest("[data-reading-flow-id]")?.getAttribute("data-reading-flow-id") || null,
          reading_flow_rank: el.getAttribute("data-reading-flow-rank") || el.closest("[data-reading-flow-rank]")?.getAttribute("data-reading-flow-rank") || null,
          reading_region: el.getAttribute("data-reading-region") || el.closest("[data-reading-region]")?.getAttribute("data-reading-region") || null,
          column_index: el.getAttribute("data-column-index") || el.closest("[data-column-index]")?.getAttribute("data-column-index") || null,
          flow_path: attrDeep(el, "data-flow-path"),
          flow_region: attrDeep(el, "data-flow-region"),
          flow_container: attrDeep(el, "data-flow-container"),
          flow_role: attrDeep(el, "data-flow-role"),
          flow_rank: attrDeep(el, "data-flow-rank"),
          flow_parent: attrDeep(el, "data-flow-parent"),
          flow_direction: attrDeep(el, "data-flow-direction"),
          ocr_orderable: flowOrderable,
          caption_of: attrDeep(el, "data-caption-of"),
          font_size: style.fontSize,
          font_family: style.fontFamily,
          is_text: isText,
          asset_id: el.getAttribute("data-asset-id"),
          asset_source: el.getAttribute("data-asset-source"),
          asset_crop: el.getAttribute("data-asset-crop"),
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
    if ((block.block_label === "footer" || block.block_label === "page_number") && (xMax - xMin < 5 || yMax - yMin < 5)) {
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

function blockTop(block) {
  return Number(block?.coordinates?.y_min ?? 0);
}

function blockLeft(block) {
  return Number(block?.coordinates?.x_min ?? 0);
}

function blockRight(block) {
  return Number(block?.coordinates?.x_max ?? 0);
}

function rolePriority(role, label) {
  const key = role || label || "";
  const priorities = {
    title: 0,
    document_title: 0,
    subtitle: 1,
    document_subtitle: 1,
    heading: 2,
    section_title: 2,
    chapter_title: 2,
    metadata: 3,
    field_label: 4,
    field_value: 5,
    body: 6,
    paragraph: 6,
    caption: 7,
    page_number: 95,
    footer: 98,
  };
  return priorities[key] ?? 50;
}

function isTopLevelTitle(block, attrs) {
  return (attrs.flow_role || block.block_label) === "title" || block.block_label === "document_title";
}

function isFooterLike(block, attrs) {
  const role = attrs.flow_role || block.block_label || "";
  return role === "footer" || role === "page_number" || block.block_label === "footer" || block.block_label === "page_number";
}

function isColumnBodyLike(block, attrs) {
  const role = attrs.flow_role || block.block_label || "";
  return ["body", "paragraph", "heading", "section_title", "note", "quote", "list_item", "metadata"].includes(role) ||
    ["paragraph", "section_title", "note", "quote", "list_item", "metadata"].includes(block.block_label || "");
}

function isColumnAnchor(block, attrs) {
  const role = attrs.flow_role || block.block_label || "";
  return ["body", "paragraph", "heading", "section_title", "note", "quote", "list_item"].includes(role) ||
    ["paragraph", "section_title", "note", "quote", "list_item"].includes(block.block_label || "");
}

function findColumnIndex(block, columns, direction) {
  if (!columns.length) return 0;
  const center = (blockLeft(block) + blockRight(block)) / 2;
  let bestIdx = 0;
  let bestDist = Infinity;
  columns.forEach((col, idx) => {
    const dist = Math.abs(center - col.center);
    if (dist < bestDist) {
      bestDist = dist;
      bestIdx = idx;
    }
  });
  if ((direction || "").toLowerCase() === "rtl") {
    return columns.length - 1 - bestIdx;
  }
  return bestIdx;
}

function detectReadingColumns(items) {
  const candidates = items.filter((item) => {
    const block = item.block;
    const attrs = block.attributes || {};
    return item.visual.band === 1 && isColumnAnchor(block, attrs);
  });
  if (candidates.length < 8) return [];
  const centers = candidates
    .map((item) => (blockLeft(item.block) + blockRight(item.block)) / 2)
    .sort((a, b) => a - b);
  const minX = centers[0];
  const maxX = centers[centers.length - 1];
  const span = maxX - minX;
  if (span < 180) return [];
  const gaps = [];
  for (let i = 1; i < centers.length; i++) {
    gaps.push({ gap: centers[i] - centers[i - 1], index: i });
  }
  const strongGaps = gaps
    .filter((g) => g.gap >= Math.max(120, span * 0.16))
    .sort((a, b) => b.gap - a.gap)
    .slice(0, 3)
    .sort((a, b) => a.index - b.index);
  if (!strongGaps.length) return [];
  const ranges = [];
  let start = 0;
  for (const g of strongGaps) {
    ranges.push(centers.slice(start, g.index));
    start = g.index;
  }
  ranges.push(centers.slice(start));
  const columns = ranges
    .filter((range) => range.length >= 2)
    .map((range) => ({
      min: range[0],
      max: range[range.length - 1],
      center: (range[0] + range[range.length - 1]) / 2,
      count: range.length,
    }));
  return columns.length >= 2 ? columns : [];
}

function visualReadingKey(block, attrs, category) {
  const y = blockTop(block);
  const x = (attrs.flow_direction || "").toLowerCase() === "rtl" ? -blockRight(block) : blockLeft(block);
  const role = rolePriority(attrs.flow_role, block.block_label);
  let band = 1;
  if (isTopLevelTitle(block, attrs)) {
    band = 0;
  } else if (isFooterLike(block, attrs)) {
    band = 9;
  }
  return { band, y, x, role };
}

function compileReadingFlow(blocks, manifestItem = {}) {
  const category = manifestItem.category || manifestItem.template_type || "";
  const regionRank = {
    masthead: 10,
    cover: 10,
    feature_head: 10,
    paper_title: 10,
    author_meta: 12,
    abstract: 14,
    keywords: 16,
    lead_story: 20,
    lead_media: category === "magazine_journal" ? 35 : 20,
    article_body: 30,
    body_columns: 30,
    secondary_stories: 30,
    figure_table: 40,
    modules: 40,
    sidebar: 50,
    bottom_strip: 70,
    references: 80,
    footnotes: 85,
    footer: 90,
    body: 30,
  };
  const visualSortCategories = new Set([
    "certificate_proof",
    "exam_paper",
    "sign_poster_scene",
    "book_page",
    "textbook_page",
    "historical_classic",
    "notice_announcement",
    "complex_form",
    "handwritten_letter",
  ]);
  const ordered = [];
  for (const block of blocks) {
    const attrs = block.attributes || {};
    const hasText = String(block.block_content || "").trim().length > 0;
    const orderable = attrs.ocr_orderable !== false && block.is_text !== false && hasText;
    if (!orderable) {
      delete block.reading_order;
      block.is_text = false;
      block.reading_group = "non_ocr";
      block.reading_role = attrs.flow_role || block.block_label || "non_ocr";
      block.reading_region = attrs.flow_region || attrs.reading_region || null;
      block.reading_flow_id = attrs.flow_path || attrs.reading_flow_id || null;
      block.reading_flow_rank = attrs.flow_rank ? Number.parseInt(attrs.flow_rank, 10) : null;
      block.reading_order_confidence = attrs.flow_path ? "template_non_ocr" : null;
      continue;
    }
    const flowRank = Number.parseInt(attrs.flow_rank || attrs.reading_flow_rank || "", 10);
    const visual = visualReadingKey(block, attrs, category);
    ordered.push({
      block,
      regionRank: regionRank[attrs.flow_region] || regionRank[attrs.reading_region] || 30,
      rank: Number.isFinite(flowRank) ? flowRank : 1000000 + Number(attrs.dom_index || 0),
      dom: Number(attrs.dom_index || 0),
      visual,
    });
  }
  const strictOrder = manifestItem.reading_order_mode === "template_strict";
  if (strictOrder) {
    ordered.sort((a, b) => (a.rank - b.rank) || (a.dom - b.dom));
  } else if (visualSortCategories.has(category)) {
    const columns = detectReadingColumns(ordered);
    ordered.sort((a, b) => {
      const ay = Math.round(a.visual.y / 18);
      const by = Math.round(b.visual.y / 18);
      const aDir = a.block.attributes?.flow_direction || "";
      const bDir = b.block.attributes?.flow_direction || "";
      const aColumn = a.visual.band === 1 ? findColumnIndex(a.block, columns, aDir) : 0;
      const bColumn = b.visual.band === 1 ? findColumnIndex(b.block, columns, bDir) : 0;
      return (
        a.visual.band - b.visual.band ||
        aColumn - bColumn ||
        ay - by ||
        a.visual.x - b.visual.x ||
        a.visual.role - b.visual.role ||
        a.dom - b.dom
      );
    });
  } else {
    ordered.sort((a, b) => a.regionRank - b.regionRank || a.rank - b.rank || a.dom - b.dom);
  }
  ordered.forEach((item, idx) => {
    const block = item.block;
    const attrs = block.attributes || {};
    block.reading_order = idx + 1;
    block.reading_group = attrs.flow_container || attrs.flow_region || attrs.reading_region || "body";
    block.reading_role = attrs.flow_role || block.block_label || "text";
    block.reading_region = attrs.flow_region || attrs.reading_region || "body";
    block.reading_flow_id = attrs.flow_path || attrs.reading_flow_id || `${block.reading_group}:${idx + 1}`;
    block.reading_flow_rank = item.rank;
    block.reading_order_confidence = attrs.flow_path ? "template_high" : "dom_fallback";
    if (attrs.flow_direction) {
      block.reading_direction = attrs.flow_direction;
    }
    if (attrs.caption_of) {
      block.caption_of = attrs.caption_of;
    }
  });
  return blocks;
}

async function computeAutoCrop(page, blocks, args, manifestItem = {}) {
  const enabled = args["auto-crop"] === true || args["auto-crop"] === "true" || args["auto-crop"] === "1";
  const tightCrop =
    manifestItem.tight_crop === true ||
    args["tight-crop"] === true ||
    args["tight-crop"] === "true" ||
    args["tight-crop"] === "1";
  const preserveFullPage =
    (manifestItem.preserve_full_page === true && !tightCrop) ||
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

  const blockRects = [];
  for (const block of blocks) {
    if (block.block_label === "footer" || block.block_label === "page_number") {
      continue;
    }
    const c = block.coordinates;
    if (c.x_max - c.x_min < 2 || c.y_max - c.y_min < 2) {
      continue;
    }
    blockRects.push(c);
  }
  const rects = tightCrop && blockRects.length
    ? blockRects
    : [...pageBox.structural_rects, ...blockRects];
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
  const padding = Number.isFinite(explicitPadding)
    ? explicitPadding
    : tightCrop
      ? Math.max(24, Math.round(dynamicPadding * 0.72))
      : Math.max(36, dynamicPadding);
  let x = Math.max(0, Math.floor(content.x_min - padding));
  let y = Math.max(0, Math.floor(content.y_min - padding));
  let xMax = Math.min(pageBox.width, Math.ceil(content.x_max + padding));
  let yMax = Math.min(pageBox.height, Math.ceil(content.y_max + padding));

  const contentHeightRatio = (content.y_max - content.y_min) / Math.max(pageBox.height, 1);
  const bottomBlankRatio = (pageBox.height - content.y_max) / Math.max(pageBox.height, 1);
  const contentWidthRatio = (content.x_max - content.x_min) / Math.max(pageBox.width, 1);
  const allowTightY = tightCrop || bottomBlankRatio > 0.28 || contentHeightRatio < 0.62;
  const allowTightX = tightCrop || contentWidthRatio < 0.72;

  if (!allowTightX && xMax - x > pageBox.width * 0.86) {
    x = 0;
    xMax = pageBox.width;
  }
  if (!allowTightY && yMax - y > pageBox.height * 0.94) {
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
    tight_crop: tightCrop,
    crop_source: tightCrop && blockRects.length ? "marked_blocks" : "structural_and_marked_blocks",
    content_height_ratio: Number(contentHeightRatio.toFixed(4)),
    bottom_blank_ratio_before_crop: Number(bottomBlankRatio.toFixed(4)),
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
      const text = (el.innerText || "").replace(/\s+/g, " ").trim();
      const label = el.getAttribute("data-label") || "text";
      const nonTextPlaceholder = !text && ["image", "answer_area"].includes(label);
      const overflow = (outsidePage || hiddenOverflow) && !nonTextPlaceholder;
      if (overflow) {
        overflowBlocks.push({
          block_id: el.getAttribute("data-block-id"),
          label,
          text: text.slice(0, 80),
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
  const blocks = compileReadingFlow(crop.enabled ? cropBlocks(rawBlocks, crop) : rawBlocks, manifestItem);

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
      version_name: manifestItem.version_name,
      language_mix_mode: manifestItem.language_mix_mode,
      target_cjk_ratio: manifestItem.target_cjk_ratio,
      chinese_topic: manifestItem.chinese_topic,
      source_version: manifestItem.source_version,
      image_assets_enabled: manifestItem.image_assets_enabled,
      reading_order_policy: manifestItem.reading_order_policy || "template_flow_v1",
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

async function closeBrowserWithTimeout(browser, timeoutMs = 5000) {
  let timer = null;
  let closed = false;
  const closePromise = browser.close().then(() => {
    closed = true;
  });
  const timeoutPromise = new Promise((resolve) => {
    timer = setTimeout(resolve, timeoutMs);
  });
  await Promise.race([closePromise, timeoutPromise]);
  if (timer) clearTimeout(timer);
  if (!closed) {
    const proc = typeof browser.process === "function" ? browser.process() : null;
    if (proc && !proc.killed) {
      proc.kill("SIGKILL");
    }
  }
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args["input-dir"]) {
    throw new Error("--input-dir is required");
  }
  const outDir = args["input-dir"];
  const languageProfile = loadLanguageProfile(args["language-profile"]);
  const manifestPath = path.join(outDir, "metadata", "html_manifest.json");
  const renderManifestPath = path.join(outDir, "metadata", "render_manifest.json");
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
      const result = await renderOne(browser, htmlPath, outDir, item, languageProfile, args);
      results.push(result);
      writeJson(renderManifestPath, results);
      console.log(`rendered ${item.document_id}`);
    }
  } finally {
    writeJson(renderManifestPath, results);
    await closeBrowserWithTimeout(browser);
  }
  writeJson(renderManifestPath, results);
}

main()
  .then(() => {
    process.exit(0);
  })
  .catch((err) => {
  console.error(err);
  process.exit(1);
});
