# 版面模板架构重构规划 · Layout Schema v3（一类一文件 + 显式版面顺序）

> 状态：待评审（先规划，评审通过后再用子 agent 并行实现）
> 目标数据版本：VL11（与 VL10/旧流程**并存**，验证通过后再删旧）

## 1. 目标与范围（已确认）

- **一类一文件**：12 类各一个结构树文件，取代现有按生产批次分组的 4 个文件（`newspaper` / `batch1` / `reading_pages` / `remaining_pages`）。
- **统一 schema + 单一分派生成器**：一套 `category_layout_tree.v3` schema；一个 `generate_layout.py` 按语种书写方向分派，取代现有 4 个横排生成器 + 1 个蒙古竖排生成器。
- **蒙古语竖排并入同一 schema/生成器**（unify_all）。
- **强制显式版面顺序（硬要求）**：每个可 OCR 块在模板里带唯一 `reading_order`；渲染器直接采用，**禁用视觉猜测回退**。
- **迁移优先，版式后调（migrate_then_tune）**：Phase 1 先把现有 12 类版式忠实迁入新 schema 并补齐显式顺序（效果对齐 VL10）；Phase 2 再逐类优化版式。

## 2. 关键现状（子 agent 调研结论）

- **无一处显式声明阅读顺序**：
  - `newspaper`：regions/components 声明，但块序由生成器 `FlowPlanner.rank++` 隐式产生。
  - `batch1`：模板只有 `layout_family`，版面结构与顺序全部硬编码在生成器。
  - `reading_pages`/`remaining_pages`：`structure[]` 只是语义标签表，真实顺序来自生成器代码执行序。
  - 蒙古 v4：无 `reading_order`，靠 `elements[]` 数组序 + `box{x,y}` 坐标推断。
- **多栏顺序脆弱**：CSS `columns:N` 是列优先、grid `repeat(N,1fr)` 是行优先，顺序依赖布局模式；渲染器对 9 类 `visualSortCategories` 还会做视觉重排回退（竖排/稀疏页易错）。
- **横竖排能否共用同一结构树**：schema 可统一（`box`/`label`/`role`/`text` 通用），但**元素组织本质不同**（竖排列数/比例与横排不同）。故：**统一 schema + 统一生成器，但横排与竖排各自保留其变体的块布局**。

## 3. v3 Schema（一类一文件）

路径：`configs/layout_templates_v3/NN_<category_id>.layout.json`（12 个）

```jsonc
{
  "schema_version": "category_layout_tree.v3",
  "category_index": 1,
  "category_id": "newspaper_page",
  "category_cn": "报纸页",
  "shared_constraints": {
    "required_labels": ["document_title", "paragraph"],
    "min_ocr_blocks": 20,
    "qa": { "reading_order_explicit": true, "overflow_blocks": 0 }
  },
  "variants": [
    {
      "variant": 1,
      "template_id": "newspaper_page_v01",
      "template_name_cn": "传统竖版日报头版",
      "layout_family": "classic_broadsheet_frontpage",
      "writing_mode": "horizontal-tb",           // 竖排变体为 "vertical-lr"
      "page": { "width": 1240, "height": 1754, "orientation": "portrait", "background": "warm_newsprint" },
      "tight_crop": true,
      "preserve_full_page": false,
      "regions": [
        { "id": "masthead", "order": 1, "layout": "stack" },
        { "id": "main", "order": 2, "layout": "columns", "columns": 3,
          "column_ratios": [1.08, 1.22, 0.72], "column_read_order": "by_direction" },
        { "id": "footer", "order": 3, "layout": "stack" }
      ],
      "blocks": [
        { "reading_order": 1, "region": "masthead", "column": 0, "role": "title",
          "label": "document_title", "ocr_orderable": true,
          "text": { "source": "title", "min_chars": 10, "max_chars": 32 } },
        { "reading_order": null, "region": "main", "column": 0, "role": "image",
          "label": "image", "ocr_orderable": false, "caption_of": null }
        // ...
      ]
    }
  ]
}
```

**核心不变式（生成 + 校验都强制）**：
- 每个 `ocr_orderable:true` 块必须有**唯一整数** `reading_order`，且整变体内构成 `1..N` 连续序列。
- 非 OCR 块（image/rule/answer_area/table_structure…）`ocr_orderable:false`、`reading_order:null`。
- `region`/`column` 只是分组与布局；书写方向（来自 language profile：ltr/rtl/vertical-lr）只影响**视觉摆放**，**不改变 `reading_order` 数字**。RTL 只是列/行视觉镜像，顺序仍由显式序号决定。
- `column_read_order:"by_direction"`：ltr 列 0→N（左→右）、rtl N→0、vertical-lr 列 0→N（左→右、列内上→下）。

## 4. 生成器架构：单一 `scripts/generate_layout.py`

- 输入：一个类文件（或全 12 类）+ language profile + 文本源。
- 按 profile 的 `writing_direction` 选取匹配 `writing_mode` 的变体集（横排语种用 horizontal-tb 变体；蒙古语用 vertical-lr 变体）。
- **布局引擎**：把 `regions`（stack/columns/grid）+ `blocks` 渲染为绝对/流式 HTML，CSS 由 writing_mode + 方向驱动（复用现有 `synthetic_text_utils` 的 vertical/rtl CSS 与字体链）。
- **顺序透传**：改造 `FlowPlanner`，直接采用模板 `reading_order`（不再自增 rank），产出权威 `data-flow-rank`。
- 产出目录结构与现有一致（`html/ images/ labels/ metadata/ reports/`），可直接接入现有渲染与 QA。

## 5. 渲染器改造（`render_table_dataset.mjs`）

- 新增**严格顺序模式**：当一页所有可排序块都带 `flow_rank` 时，**只按 `flow_rank` 排序**，跳过 `visualSortCategories` 视觉重排回退。
- v3 恒带显式序号 → 恒走严格模式 → 满足"清晰版面顺序"硬要求，且横排/RTL/竖排统一可靠。
- 旧 v2 数据仍可走原视觉回退（并存期兼容）。

## 6. 顺序即新逻辑：VL11 顺序由 v3 模板主动定义（不参考 VL10）

**决策**：VL10 的顺序不作为参考。VL11 的阅读顺序是我们在 v3 模板里**主动设计**的一套新逻辑，`reading_order` 由下方规则**显式编排**，与旧产物无关。

### 6.1 显式排序规则（新逻辑，横/RTL/竖排统一适用）

对每个变体，`reading_order` 按以下确定性规则编排为 `1..N`：
1. **先按 region 的 `order`**（区域从主到次：报头/标题区 → 正文区 → 侧栏 → 页脚）。
2. **区域内按 column**：
   - `ltr`：列 0→N（左→右）；`rtl`：列 N→0（右→左）；`vertical-lr`（蒙古）：列 0→N（左→右）。
3. **列内按块的自然先后**（横排上→下；竖排上→下）。
4. **图注 caption 紧跟其所属图之后**（`caption_of`），图本身不编号。
5. **非 OCR 块**（image/rule/divider/answer_area/table_structure）`ocr_orderable:false`、不参与编号。
6. 表格：默认按行主序（row-major）给单元格文本编号；表单 key-value 按"标签→值"成对顺序。

关键：`reading_order` 是**方向无关的绝对序号**。RTL / 竖排只改变列/行的**视觉摆放**，序号仍严格由上述规则决定 → 渲染器直接采用，不做任何视觉猜测。

### 6.2 结构来源（版式 Phase 1 忠实、顺序全新）

- **版式结构**（有哪些 region/block/role、几栏、页面尺寸）：沿用现有 12 类既有设计（已由调研逐类记录），保证 VL11 观感稳定。
- **顺序**：一律按 6.1 规则**重新编排**并写死在模板里；**不从 VL10/旧生成器提取**。
- 由子 agent 逐类逐变体产出 v3 JSON；每类人工抽检 1–2 变体，确认版式合理 + 顺序符合 6.1。
- 蒙古竖排变体：版式参考 `mongolian_vertical_templates_v4`（列位置来自其 `box.x`），顺序按 6.1（列 0→N、列内上→下）显式编排。

## 7. 校验（顺序变成硬门禁）

- 新增/加强 `qa_reading_flow` 断言：`reading_order` 唯一、连续、覆盖全部可 OCR 块；非 OCR 块无序号；渲染后 label 的 `reading_order` 与模板一致（`template_high`，无 `dom_fallback`）。
- 保留 overflow=0、脚本比率、字体无方块等既有 QA。

## 8. 落地与并存（VL11）

- 新增：`configs/layout_templates_v3/`（12 文件）、`scripts/generate_layout.py`、渲染器严格模式、`tools/convert_v2_to_v3.py`、校验增强。
- `run_full_generation.py` 增 `--schema {v2,v3}`（默认暂 v2）；`--schema v3` 产出 **VL11**。
- **并存**：保留 v2 的 4 文件 + 4 生成器 + 蒙古 v3 生成器，直到 VL11 全 7 语种验证通过；随后统一删除旧件并把默认切到 v3。
- `.gitignore` 已覆盖 `VL[0-9]*`，VL11 自动忽略。

## 9. 子 agent 并行实现分工（评审通过后执行）

- **中枢（主）**：`generate_layout.py` 布局引擎 + `FlowPlanner` 改造 + 渲染器严格模式 + `run_full_generation.py --schema` + 校验增强；先做 **newspaper 单类 pilot** 打通端到端并锁定 schema/生成器/渲染器。
- **Agent A**：类 01–04 的 v3 文件（横排变体，按 6.1 显式编排顺序）。
- **Agent B**：类 05–07 v3 文件。
- **Agent C**：类 08–12 v3 文件。
- **Agent D**：蒙古竖排变体（12 类 vertical-lr），并入各类文件的 `variants`。
- 分工前提：pilot 打通、schema 定稿后再 fan-out，避免子 agent 对着未验证的 schema 产文件。

## 10. 里程碑

1. 评审本规划（当前）。
2. schema 定稿 + 转换器 + 1 类打通（newspaper）端到端 smoke。
3. 12 类横排 + 蒙古竖排全量转换。
4. `generate_layout.py` + 渲染器严格模式接入 `run_full_generation.py --schema v3`。
5. VL11 全量 + 严格 QA + 抽检。
6. 验证通过 → 删旧件、默认切 v3。
