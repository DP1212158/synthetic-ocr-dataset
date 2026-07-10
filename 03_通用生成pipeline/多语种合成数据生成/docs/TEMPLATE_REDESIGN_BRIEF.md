# 合成 OCR 数据集「版面模板」精致化重设计 — 任务说明书

> 交接给执行 agent 的完整任务书。只改模板 JSON；严禁改任何 .py/.mjs 脚本；严禁跑全量重生成；不动现有 VL11 产物。

## 1. 背景
仓库根目录：`/mnt/dengpenglongyi/synthetic-ocr-dataset`

多语种合成 OCR 数据集工程：用 JSON「结构树」模板 → HTML → Chromium 渲染成 图片 + 标注。两条渲染管线：

- 横排语种（藏/壮/朝/白/维/哈，文字横排）：通用渲染器
  `03_通用生成pipeline/多语种合成数据生成/scripts/generate_layout.py`，
  读取 `configs/layout_templates_v3/*.layout.json`，flex 流式布局。
- 蒙古语（传统蒙古文，竖排：字上→下、列左→右）：专用渲染器
  `scripts/generate_mongolian_vertical_from_json_v3.py`，
  读取 `02_语种工程资源/蒙古语/03_合成数据生成/configs/mongolian_vertical_templates_v4/*/*.json`，绝对定位布局。

**渲染器已扩展好视觉词汇（本任务只改模板 JSON）。**

## 2. 目标
当前版面「粗糙、丑陋、只有纯文本 + 灰色图片占位」。要把每类模板重设计成 **贴合该类别、精致、元素丰富** 的版面（可适度留白，不必填满，但要美观、有层次、有该类别特征）。

## 3. 要改的文件
横排：`03_通用生成pipeline/多语种合成数据生成/configs/layout_templates_v3/` 下 12 个文件，每个 9 个 variant（6 个 `orientation:landscape` + 3 个 `orientation:portrait`）：
`01_newspaper_page 02_certificate_proof 03_exam_paper 04_sign_poster_scene 05_book_page 06_textbook_page 07_magazine_journal 08_academic_paper 09_historical_classic 10_notice_announcement 11_complex_form 12_handwritten_letter`

蒙古：`02_语种工程资源/蒙古语/03_合成数据生成/configs/mongolian_vertical_templates_v4/` 下 12 个类目文件夹，每个 6 个 JSON（共 72）。

保持不变：variant 数量与编号、`orientation` 标签、`writing_mode`、`template_id`、文件名、蒙古模板的 `category_id/category_cn/folder`。先读 2–3 个现有文件对齐 schema 再改。

## 4. 通用横排渲染器已支持的「视觉词汇」（要充分使用）
- region 级字段 `"visual"`：`"band"`（accent 底色页眉/报头带，白字）、`"softband"`（accent 左边框浅底引注块）、`"card"`（白底描边卡片）、`"framed"`（accent 描边框）、`"footer"`（上分割线页脚条）。例：`{"id":"masthead","order":1,"layout":"stack","visual":"band"}`。
- variant 的 `page` 加 `"frame"`：`"framed"`（双线 accent 页框）/`"inset"`（内细框）/`"both"`。适合证书/古籍。
- region `layout:"grid"`：渲染成带边框的表格单元；表头单元格在 block 上加 `"th":true`。适合考卷分数表、复杂表单。
- 新增非 OCR block label：`"seal"`/`"stamp"`（accent 圆形印章，可选 `"seal_text"`、`"size"`）、`"divider"`（accent 分割线，可选 `"thin":true`）、`"rule"`。
- block 标志：`"accent":true`（标题/小标题用强调色）；表单字段行用 label `"field_label"` + `"field_value"`（value 自带下划线）。
- variant 的 `style_tokens` 可设 `accent/accent2/paper/ink/band_ink`，为每类挑合适配色。

## 5. 蒙古竖排管线要点
- **图片自动填充**：任何 `kind` 为 `image/photo/figure`（或 class 含 `image-fill`）的元素会被自动填充为真实 COCO 图片，无需手动指定路径。该有图的类目要放 1–2 个 image 元素。
- 已有可用 CSS class：`box boxed ornate rule-v rule-h stamp accent soft-fill note-fill image-fill`。
- **解决「太空」**：文本元素要填满框的 ~80–90%。竖排容量 ≈ floor(w/(字号×1.4)) 列 × floor(h/字号) 字；字号 title=34 subtitle=24 body=20 small=16 tiny=13 px；`text.max_chars ≈ 0.85×容量`、`min_chars ≈ 0.65×容量`，**不得超过容量（溢出会渲染成超长条）**。稀疏处加列/加块。
- 目标 portrait 长宽比（裁剪后 高/宽）∈ [1.35, 1.7]，无极端 >1.9。

## 6. 各类别设计意图
- 报纸 newspaper：报头 band（刊名+日期/期号）+ 多栏正文 + 小标题 + 图文 + 栏间分割线 + 页脚。
- 证书 certificate：`frame:"both"` + 居中 accent 标题 + 正文 + 字段行 + 印章 seal + 落款/日期。
- 考卷 exam：header band（校名/卷名 + grid 分数表 th 表头）+ 编号 question + answer_area + 分割线。
- 标牌海报 sign_poster：大号 accent 标题 + 副标 + 少量 list/note + 可选图；强对比、多留白。
- 书籍 book：页眉/页脚 + 多段正文 + 小节标题 + 偶尔图注；文气整洁。
- 教科书 textbook：accent 小节标题 + 编号列表 + softband 讲解/例题框 + 图注 + 练习；活泼整洁。
- 杂志 magazine：大特稿标题 + 副题 + 分栏 + 主图 + 图注 + 引语 softband + 署名。
- 学术 academic：标题 + 作者 + 摘要（card/softband）+ 小节 + 正文 + grid 数据表(th) + 图注 + 参考文献；克制。
- 古籍 historical：`frame:"both"` + 竖版式边框版心（文字仍横排）+ 标题 + 分割线 + 小注；古典。
- 公告 notice：公文 band 头（通知 + 文号）+ 正文 + 落款/日期 footer + 红色 seal「公章」；公文体。
- 复杂表单 complex_form：标题 band + 多字段行 + grid 表格(th 表头 + 数据行)+ answer_area/勾选 + 印章 + 签名行；密而整。
- 手写信 handwritten：称呼 + 正文段落 + 结尾/署名/日期 + softband 便签；疏朗、personal。

## 7. 硬约束（会被脚本校验，必须满足）
- 每个「可 OCR」block（label 不在 `{image,photo,figure,answer_area,rule,divider,decorative_rule,table_structure,visual,seal,stamp}`）必须有唯一且连续的 `reading_order` 1..N。
- 非 OCR block 设 `"ocr_orderable":false` 且**无** `reading_order`；image/figure 要有数值 `height`。
- 任何 `caption` block 必须在 blocks 数组里**紧跟**在 image/figure 之后，或紧跟在 `region=="table"`/grid 区块之后。
- 每个 block 的 `region` 必须是该 variant 声明的 region id；`column` < 该 region 的 columns。
- 每类最少 OCR 块：newspaper≥18、certificate≥7、exam≥20、sign_poster≥6、book≥8、textbook≥10、magazine≥9、academic≥12、historical≥10、notice≥7、complex_form≥18、handwritten≥10。
- portrait variant 渲染出来必须明显「高>宽」（h/w>1.2）。
- 不破坏 RTL：维/哈方向由渲染器的 `direction:rtl` 容器自动处理（多栏右→左），模板照常用 landscape/portrait 即可，**不要手动反转栏序**。

## 8. 自检方法（渲染到 /tmp，反复迭代，绝不动真实 VL11 产物）
环境：Node 20 在 `/root/tools/node20/bin`（渲染必需，Node 12 跑不了 playwright）；系统 python3 有 PIL/playwright。

横排（以藏语 records/profile 测；RTL 效果可再用维吾尔 profile 测一次）：
```bash
export PATH=/root/tools/node20/bin:$PATH
SCR=/mnt/dengpenglongyi/synthetic-ocr-dataset/03_通用生成pipeline/多语种合成数据生成/scripts
LAY=$SCR/../configs/layout_templates_v3
REC=/mnt/dengpenglongyi/synthetic-ocr-dataset/02_语种工程资源/藏语/01_文本数据获取/data/vl3_long_text_sources/records.jsonl
PROF=/mnt/dengpenglongyi/synthetic-ocr-dataset/02_语种工程资源/藏语/03_合成数据生成/configs/tibetan_language_profile.json
ZH=/mnt/dengpenglongyi/synthetic-ocr-dataset/00_共享资源/中文语料/zh_content_bank.json
python3 "$SCR/generate_layout.py" --templates-dir "$LAY" --text-jsonl "$REC" --language-profile "$PROF" \
  --output-root /tmp/chk --version-name VT --zh-bank "$ZH" --only-category <category_id>
node "$SCR/render_table_dataset.mjs" --input-dir /tmp/chk/<对应中文文件夹> --language-profile "$PROF" --auto-crop true --tight-crop true
# 打开 /tmp/chk/*/images/*.png 目视判断精致度；确认 JSON 合法、每文件 9 变体、reading_order 连续、portrait 图 h/w>1.2；完事清理 /tmp/chk
```

蒙古（用蒙古 records/profile，并传 --image-assets-dir 才能看到真图）：
```bash
DIR=/mnt/dengpenglongyi/synthetic-ocr-dataset/02_语种工程资源/蒙古语/03_合成数据生成/configs/mongolian_vertical_templates_v4
MREC=/mnt/dengpenglongyi/synthetic-ocr-dataset/02_语种工程资源/蒙古语/01_文本数据获取/data/vl3_long_text_sources/records.jsonl
MPROF=/mnt/dengpenglongyi/synthetic-ocr-dataset/02_语种工程资源/蒙古语/03_合成数据生成/configs/mongolian_language_profile.json
ASSETS=/mnt/dengpenglongyi/synthetic-ocr-dataset/04_共享图片资产
python3 "$SCR/generate_mongolian_vertical_from_json_v3.py" --text-jsonl "$MREC" --output-root /tmp/mchk \
  --language-profile "$MPROF" --templates-root "$DIR" --min-records 30 --seed 5 --version-name VT --image-assets-dir "$ASSETS"
node "$SCR/render_table_dataset.mjs" --input-dir /tmp/mchk/<类目文件夹> --language-profile "$MPROF" --auto-crop true --tight-crop true
# 目视 + 校验：无极端长宽比(>1.9)、真图出现、填充充分；清理 /tmp/mchk
```

结构校验片段（横排）：
```python
import json,glob
NON={"image","photo","figure","answer_area","rule","divider","decorative_rule","table_structure","visual","seal","stamp"}
for f in glob.glob("/mnt/dengpenglongyi/synthetic-ocr-dataset/03_通用生成pipeline/多语种合成数据生成/configs/layout_templates_v3/*.layout.json"):
    d=json.load(open(f)); assert len(d["variants"])==9, f
    for v in d["variants"]:
        o=[b["reading_order"] for b in v["blocks"] if b["label"] not in NON]
        assert sorted(o)==list(range(1,len(o)+1)), (f,v["variant"],o)
print("ALL OK")
```

## 9. 交付要求
- 逐类改、每改完就渲染目视迭代，直到「精致、贴类别、无溢出、方向比合规、结构校验通过」。
- 报告：每类做了什么设计、用了哪些新视觉特征、自检结果（结构 OK + 目视结论 + 无极端长宽比）。
- 只改模板 JSON；不改脚本；不跑全量 `run_full_generation`；不动现有 VL11 数据。

## 10. 环境提醒
- 出网不稳定、后端偶发超时；渲染必须先 `export PATH=/root/tools/node20/bin:$PATH`。
- 若用多子 agent 并行：按类目分片、每片独占不同文件、避免同时起过多导致后端超时空转（详见精简版交接说明）。
