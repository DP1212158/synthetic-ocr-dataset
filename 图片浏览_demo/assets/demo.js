const state = {
  manifest: null,
  datasets: {},
  versions: [],
  version: null,
  languageId: null,
  categoryId: null,
  showOrderOverlay: false,
  labelCache: new Map(),
};

const els = {
  generatedMeta: document.querySelector("#generatedMeta"),
  versionNav: document.querySelector("#versionNav"),
  languageNav: document.querySelector("#languageNav"),
  categoryNav: document.querySelector("#categoryNav"),
  currentTitle: document.querySelector("#currentTitle"),
  currentPath: document.querySelector("#currentPath"),
  versionStat: document.querySelector("#versionStat"),
  categoryStat: document.querySelector("#categoryStat"),
  languageStat: document.querySelector("#languageStat"),
  toggleOrderOverlay: document.querySelector("#toggleOrderOverlay"),
  imageGrid: document.querySelector("#imageGrid"),
  previewDialog: document.querySelector("#previewDialog"),
  previewImage: document.querySelector("#previewImage"),
  previewName: document.querySelector("#previewName"),
  previewPath: document.querySelector("#previewPath"),
  closePreview: document.querySelector("#closePreview"),
};

function getCurrentLanguages() {
  return state.datasets[state.version] || [];
}

function getCurrentLanguage() {
  return getCurrentLanguages().find((language) => language.id === state.languageId);
}

function getCurrentCategory() {
  const language = getCurrentLanguage();
  if (!language) return null;
  return language.categories.find((category) => category.id === state.categoryId);
}

function button(label, count, active, onClick) {
  const node = document.createElement("button");
  node.type = "button";
  node.className = `nav-button${active ? " active" : ""}`;

  const labelNode = document.createElement("span");
  labelNode.textContent = label;
  const countNode = document.createElement("small");
  countNode.textContent = count;
  node.append(labelNode, countNode);

  node.addEventListener("click", onClick);
  return node;
}

function selectVersion(version) {
  if (state.version === version) return;
  state.version = version;
  const languages = getCurrentLanguages();
  const firstLanguage = languages.find((language) => language.image_count > 0) || languages[0];
  state.languageId = firstLanguage?.id ?? null;
  state.categoryId = firstLanguage?.categories[0]?.id ?? null;
  state.labelCache.clear();
  render({ resetScroll: true });
}

function renderVersionNav() {
  if (!els.versionNav) return;
  els.versionNav.replaceChildren();
  state.versions.forEach((version) => {
    const languages = state.datasets[version] || [];
    const total = languages.reduce((sum, language) => sum + language.image_count, 0);
    els.versionNav.appendChild(
      button(version, `${total} 张`, version === state.version, () => selectVersion(version))
    );
  });
}

function renderLanguageNav() {
  els.languageNav.replaceChildren();
  getCurrentLanguages().forEach((language) => {
    els.languageNav.appendChild(
      button(
        `${language.name}`,
        `${language.image_count} 张`,
        language.id === state.languageId,
        () => {
          state.languageId = language.id;
          state.categoryId = language.categories[0]?.id ?? null;
          render({ resetScroll: true });
        }
      )
    );
  });
}

function renderCategoryNav() {
  const language = getCurrentLanguage();
  els.categoryNav.replaceChildren();
  if (!language) return;

  language.categories.forEach((category) => {
    els.categoryNav.appendChild(
      button(category.name, `${category.image_count} 张`, category.id === state.categoryId, () => {
        state.categoryId = category.id;
        render({ resetScroll: true });
      })
    );
  });
}

function renderSummary() {
  const language = getCurrentLanguage();
  const category = getCurrentCategory();

  if (!language || !category) {
    els.currentTitle.textContent = "暂无可浏览图片";
    els.currentPath.textContent = "请先生成 image_manifest.json";
    els.versionStat.textContent = "-";
    els.categoryStat.textContent = "-";
    els.languageStat.textContent = "-";
    els.toggleOrderOverlay.disabled = true;
    return;
  }

  els.currentTitle.textContent = `${language.name} / ${category.name}`;
  els.currentPath.textContent = category.source_path;
  els.versionStat.textContent = language.version;
  els.categoryStat.textContent = `${category.image_count}`;
  els.languageStat.textContent = `${language.image_count}`;
  const hasLabels = category.images.some((image) => image.label_path);
  els.toggleOrderOverlay.disabled = !hasLabels;
  els.toggleOrderOverlay.classList.toggle("active", state.showOrderOverlay);
  els.toggleOrderOverlay.textContent = !hasLabels ? "无顺序标签" : state.showOrderOverlay ? "隐藏顺序" : "显示顺序";
}

function imageCard(image, index, total) {
  const card = document.createElement("article");
  card.className = "image-card";

  const imageButton = document.createElement("button");
  imageButton.type = "button";
  imageButton.className = "image-button";
  imageButton.title = "点击放大查看";
  imageButton.addEventListener("click", () => openImagePreview(image));

  const img = document.createElement("img");
  img.src = image.thumb_path || image.path;
  img.alt = image.filename;
  img.loading = index === 0 ? "eager" : "lazy";
  img.decoding = "async";
  if (image.width && image.height) {
    img.width = image.width;
    img.height = image.height;
  }
  img.addEventListener("load", () => drawOrderOverlay(imageButton, img, image));
  imageButton.appendChild(img);

  const overlay = document.createElement("div");
  overlay.className = "order-overlay";
  overlay.hidden = true;
  imageButton.appendChild(overlay);

  const meta = document.createElement("div");
  meta.className = "image-meta";

  const name = document.createElement("strong");
  name.textContent = `第 ${index + 1}/${total} 张 · ${image.filename}`;
  const sourcePath = document.createElement("span");
  sourcePath.textContent = image.source_path;
  meta.append(name, sourcePath);

  card.append(imageButton, meta);
  return card;
}

function renderImages({ resetScroll = false } = {}) {
  const category = getCurrentCategory();
  els.imageGrid.replaceChildren();

  if (!category || category.images.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "这个类别暂时没有可加载的图片。";
    els.imageGrid.appendChild(empty);
    return;
  }

  category.images.forEach((image, index) => {
    els.imageGrid.appendChild(imageCard(image, index, category.images.length));
  });

  if (resetScroll) {
    els.imageGrid.scrollTo({ top: 0, left: 0, behavior: "auto" });
  }
}

function openImagePreview(image) {
  els.previewName.textContent = image.filename;
  els.previewPath.textContent = image.source_path;
  els.previewImage.src = image.path;
  els.previewImage.alt = image.filename;

  if (typeof els.previewDialog.showModal === "function") {
    els.previewDialog.showModal();
  } else {
    window.open(image.path, "_blank");
  }
}

function orderValue(block, fallbackIndex) {
  const rawValue = block.reading_order ?? block.order ?? fallbackIndex + 1;
  const parsed = Number.parseInt(rawValue, 10);
  return Number.isFinite(parsed) ? parsed : fallbackIndex + 1;
}

function blockCoordinates(block) {
  const coordinates = block.coordinates;
  if (!coordinates) return null;

  const xMin = Number(coordinates.x_min);
  const yMin = Number(coordinates.y_min);
  const xMax = Number(coordinates.x_max);
  const yMax = Number(coordinates.y_max);
  if (![xMin, yMin, xMax, yMax].every(Number.isFinite)) return null;
  if (xMax <= xMin || yMax <= yMin) return null;

  return { xMin, yMin, xMax, yMax };
}

function hasVisibleText(block) {
  return typeof block.block_content === "string" && block.block_content.trim().length > 0;
}

function blockPolygon(block, coordinates) {
  // Prefer the tight rotated quadrilateral injected for augmented versions.
  const poly = block.polygon;
  if (Array.isArray(poly) && poly.length >= 3) {
    const points = poly
      .map((p) => (Array.isArray(p) ? [Number(p[0]), Number(p[1])] : [Number(p.x), Number(p.y)]))
      .filter((p) => Number.isFinite(p[0]) && Number.isFinite(p[1]));
    if (points.length >= 3) return points;
  }
  // Fall back to the axis-aligned box corners.
  const { xMin, yMin, xMax, yMax } = coordinates;
  return [
    [xMin, yMin],
    [xMax, yMin],
    [xMax, yMax],
    [xMin, yMax],
  ];
}

async function loadLabel(image) {
  if (!image.label_path) return null;
  if (state.labelCache.has(image.label_path)) {
    return state.labelCache.get(image.label_path);
  }

  const labelPromise = fetch(image.label_path, { cache: "no-store" })
    .then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return response.json();
    })
    .catch((error) => {
      console.warn("Label load failed", image.label_path, error);
      return null;
    });
  state.labelCache.set(image.label_path, labelPromise);
  return labelPromise;
}

async function drawOrderOverlay(imageButton, img, image) {
  const overlay = imageButton.querySelector(".order-overlay");
  if (!overlay) return;

  overlay.replaceChildren();
  overlay.hidden = !state.showOrderOverlay;
  if (!state.showOrderOverlay || !image.label_path || !img.naturalWidth || !img.naturalHeight) return;

  const label = await loadLabel(image);
  if (!label || !Array.isArray(label.blocks)) return;

  // Coordinates in labels are in ORIGINAL pixel space. When the grid shows a
  // downscaled thumbnail, img.naturalWidth is the thumb size, so prefer the
  // original dimensions carried in the manifest for correct overlay scaling.
  const baseWidth = image.width || img.naturalWidth;
  const baseHeight = image.height || img.naturalHeight;

  const imageRect = img.getBoundingClientRect();
  const buttonRect = imageButton.getBoundingClientRect();
  overlay.style.left = `${imageRect.left - buttonRect.left}px`;
  overlay.style.top = `${imageRect.top - buttonRect.top}px`;
  overlay.style.width = `${imageRect.width}px`;
  overlay.style.height = `${imageRect.height}px`;

  const blocks = label.blocks
    .map((block, index) => ({ block, index, coordinates: blockCoordinates(block) }))
    .filter((item) => item.coordinates && item.block?.is_text !== false && hasVisibleText(item.block))
    .sort((a, b) => orderValue(a.block, a.index) - orderValue(b.block, b.index));

  // Draw as an SVG so we can render the tight rotated quadrilateral (block.polygon,
  // present in geometrically augmented versions like VL12) instead of a loose
  // axis-aligned rectangle. viewBox handles scaling from original pixels to display.
  const SVG_NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "order-svg");
  svg.setAttribute("width", `${imageRect.width}`);
  svg.setAttribute("height", `${imageRect.height}`);
  svg.setAttribute("viewBox", `0 0 ${baseWidth} ${baseHeight}`);
  svg.setAttribute("preserveAspectRatio", "none");
  const fontSize = Math.max(11, baseWidth / 55);

  blocks.forEach(({ block, index, coordinates }) => {
    const points = blockPolygon(block, coordinates);
    const pointsAttr = points.map((p) => `${p[0]},${p[1]}`).join(" ");

    const poly = document.createElementNS(SVG_NS, "polygon");
    poly.setAttribute("points", pointsAttr);
    poly.setAttribute("class", "order-poly");
    poly.setAttribute("vector-effect", "non-scaling-stroke");
    const titleNode = document.createElementNS(SVG_NS, "title");
    titleNode.textContent = block.block_content || block.block_label || block.block_id || "";
    poly.appendChild(titleNode);
    svg.appendChild(poly);

    // Order badge anchored at the polygon's top-left-most vertex.
    const anchor = points.reduce((best, p) => (p[1] < best[1] || (p[1] === best[1] && p[0] < best[0]) ? p : best), points[0]);
    const label = `${orderValue(block, index)}`;
    const badgeW = fontSize * (0.72 * label.length + 0.5);
    const badgeH = fontSize * 1.25;
    const bx = Math.min(Math.max(anchor[0], 0), baseWidth - badgeW);
    const by = Math.min(Math.max(anchor[1], 0), baseHeight - badgeH);

    const rect = document.createElementNS(SVG_NS, "rect");
    rect.setAttribute("x", `${bx}`);
    rect.setAttribute("y", `${by}`);
    rect.setAttribute("width", `${badgeW}`);
    rect.setAttribute("height", `${badgeH}`);
    rect.setAttribute("rx", `${fontSize * 0.25}`);
    rect.setAttribute("class", "order-badge-bg");
    svg.appendChild(rect);

    const text = document.createElementNS(SVG_NS, "text");
    text.setAttribute("x", `${bx + badgeW / 2}`);
    text.setAttribute("y", `${by + badgeH / 2}`);
    text.setAttribute("font-size", `${fontSize}`);
    text.setAttribute("text-anchor", "middle");
    text.setAttribute("dominant-baseline", "central");
    text.setAttribute("class", "order-badge-text");
    text.textContent = label;
    svg.appendChild(text);
  });

  overlay.appendChild(svg);
}

function redrawVisibleOverlays() {
  els.imageGrid.querySelectorAll(".image-button").forEach((imageButton) => {
    const img = imageButton.querySelector("img");
    const imagePath = img?.getAttribute("src");
    const category = getCurrentCategory();
    const image = category?.images.find(
      (item) => item.thumb_path === imagePath || item.path === imagePath
    );
    if (img && image) drawOrderOverlay(imageButton, img, image);
  });
}

function closePreview() {
  if (els.previewDialog.open) {
    els.previewDialog.close();
  }
}

function clearPreviewImage() {
  els.previewImage.removeAttribute("src");
  els.previewImage.alt = "";
}

function render(options = {}) {
  renderVersionNav();
  renderLanguageNav();
  renderCategoryNav();
  renderSummary();
  renderImages(options);
}

function navigateCategory(offset) {
  const language = getCurrentLanguage();
  if (!language || language.categories.length === 0) return;

  const currentIndex = language.categories.findIndex((category) => category.id === state.categoryId);
  const nextIndex = Math.min(Math.max(currentIndex + offset, 0), language.categories.length - 1);
  if (nextIndex === currentIndex) return;

  state.categoryId = language.categories[nextIndex].id;
  render({ resetScroll: true });
}

function navigateLanguage(offset) {
  const languages = getCurrentLanguages();
  if (languages.length === 0) return;

  const currentIndex = languages.findIndex((language) => language.id === state.languageId);
  const nextIndex = Math.min(Math.max(currentIndex + offset, 0), languages.length - 1);
  if (nextIndex === currentIndex) return;

  const language = languages[nextIndex];
  state.languageId = language.id;
  state.categoryId = language.categories[0]?.id ?? null;
  render({ resetScroll: true });
}

function navigateVersion(offset) {
  if (state.versions.length === 0) return;
  const currentIndex = state.versions.indexOf(state.version);
  const nextIndex = Math.min(Math.max(currentIndex + offset, 0), state.versions.length - 1);
  if (nextIndex !== currentIndex) selectVersion(state.versions[nextIndex]);
}

function handleKeyboard(event) {
  if (els.previewDialog.open) return;
  if (event.target instanceof Element && event.target.closest("button, dialog")) return;

  if (event.key === "ArrowLeft") {
    navigateCategory(-1);
  } else if (event.key === "ArrowRight") {
    navigateCategory(1);
  } else if (event.key === "Home") {
    els.imageGrid.scrollTo({ top: 0, left: 0, behavior: "smooth" });
  } else if (event.key === "[") {
    navigateLanguage(-1);
  } else if (event.key === "]") {
    navigateLanguage(1);
  } else if (event.key === "," || event.key === "-") {
    navigateVersion(-1);
  } else if (event.key === "." || event.key === "=") {
    navigateVersion(1);
  }
}

async function init() {
  try {
    let manifest = window.__IMAGE_MANIFEST__ || null;
    if (!manifest) {
      const response = await fetch("./data/image_manifest.json", { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      manifest = await response.json();
    }
    state.manifest = manifest;

    // Multi-version manifest, with backward-compatible fallback to a single
    // {languages: [...]} payload.
    if (manifest.datasets && Array.isArray(manifest.versions) && manifest.versions.length) {
      state.datasets = manifest.datasets;
      state.versions = manifest.versions;
      state.version = manifest.default_version || manifest.versions[0];
    } else {
      const legacyVersion = manifest.languages?.[0]?.version || "current";
      state.datasets = { [legacyVersion]: manifest.languages || [] };
      state.versions = [legacyVersion];
      state.version = legacyVersion;
    }

    const languages = getCurrentLanguages();
    const firstLanguage = languages.find((language) => language.image_count > 0) || languages[0];
    state.languageId = firstLanguage?.id ?? null;
    state.categoryId = firstLanguage?.categories[0]?.id ?? null;

    const totalImages = languages.reduce((sum, language) => sum + language.image_count, 0);
    els.generatedMeta.textContent =
      `索引生成时间：${state.manifest.generated_at}，` +
      `共 ${state.versions.length} 个版本（${state.versions.join(" / ")}）。` +
      `当前 ${state.version}：${languages.length} 个语种、${totalImages} 张图片。`;
    render({ resetScroll: true });
  } catch (error) {
    els.generatedMeta.textContent = `读取索引失败：${error.message}`;
    els.currentTitle.textContent = "无法加载 demo";
    els.currentPath.textContent = "请先运行 scripts/build_image_manifest.py";
  }
}

els.closePreview.addEventListener("click", closePreview);
els.previewDialog.addEventListener("close", clearPreviewImage);
els.previewDialog.addEventListener("click", (event) => {
  if (event.target === els.previewDialog) closePreview();
});
els.toggleOrderOverlay.addEventListener("click", () => {
  state.showOrderOverlay = !state.showOrderOverlay;
  renderSummary();
  redrawVisibleOverlays();
});
window.addEventListener("resize", redrawVisibleOverlays);
document.addEventListener("keydown", handleKeyboard);

init();
