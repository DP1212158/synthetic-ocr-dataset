# 蒙古语 Wikipedia 文本获取评估（2026-06-30）

## 结论

蒙古语 Wikipedia 可以作为第一批“版面模板造数据”的文本来源，尤其适合生成横排、西里尔蒙古文、百科类正文版面。它的站点规模足够启动流程：当前接口返回约 27,743 篇文章、约 10,424,929 个检索词量。

但它不是传统竖排蒙古文数据源。本次样本的传统蒙古文 Unicode 区段占比接近 0，说明 `mn.wikipedia.org` 主要提供西里尔蒙古文。如果项目目标包含内蒙古常见的传统蒙古文竖排版式，必须继续补充传统蒙古文网页、教材、报刊、OCR 或转写后人工质检文本。

## 已完成内容

项目目录：

```text
/Users/dp/Downloads/中央民族大学合作项目/文本数据获取_20260630
```

已保存：

- `scripts/collect_wikipedia_text.py`：通用 Wikipedia 文本采集器。
- `scripts/run_mn_wikipedia_sample.sh`：顺序页面采样脚本。
- `scripts/run_mn_wikipedia_random_sample.sh`：随机页面采样脚本。
- `configs/mn_wikipedia_api_sample.json`：蒙古语 Wikipedia 采集配置和代理说明。
- `data/mn_wikipedia_api_sample_20260630/`：顺序采样结果。
- `data/mn_wikipedia_random_sample_20260630/`：随机采样结果。
- `logs/`：采集运行日志。

## 采集结果对比

| 采样方式 | 扫描页面 | 有效页面 | 段落数 | 总字符数 | 平均段落字符数 | 传统蒙古文占比 | 错误数 |
|---|---:|---:|---:|---:|---:|---:|---:|
| 顺序 allpages | 300 | 14 | 666 | 87,295 | 131.1 | 0.0 | 0 |
| 随机 random | 300 | 10 | 207 | 54,564 | 263.6 | 0.0002 | 0 |

顺序采样段落更多，但早期页面偏日期、数字和符号标题，代表性一般。随机采样段落更少，但更能代表真实站点分布。两者共同说明：蒙古语 Wikipedia 能抓到可用正文，但有效长文密度不高，正式扩容时需要更大的页面扫描量或改用 Wikimedia dumps。

## 数据格式

每条记录保存为 JSONL/CSV，核心字段包括：

- `language_code`
- `language_name`
- `script_note`
- `source`
- `title`
- `pageid`
- `paragraph_index`
- `chars`
- `url`
- `text`
- `license_note`
- `crawl_time_utc`
- `cyrillic_ratio`
- `vertical_mongolian_ratio`
- `latin_ratio`

这些字段可以直接接到后续版面模板生成器：用 `text` 填版面，用 `title/source/url/license_note` 保留来源追踪。

## 对后续造数据的建议

1. 如果只是验证模板流程，当前两批样本已经够用。
2. 如果要生成几千到几万张横排蒙古语样本，可以继续用 API 随机采样扩大规模，或下载 Wikimedia dumps 做离线过滤。
3. 如果要模拟真实文档版面，建议混合 Wikipedia、新闻、教材、政府公告、词典解释等来源，避免文本题材过窄。
4. 如果目标是传统蒙古文竖排版面，不应依赖 `mn.wikipedia.org`，需要另开传统蒙古文数据源采集任务。
5. 后续生成数据集时要保留来源和许可证说明，尤其是 Wikipedia 文本的署名与共享要求。

## 推荐下一步

先用 `data/mn_wikipedia_random_sample_20260630/records.jsonl` 接到版面模板生成流程，做 20-50 张样图验证字体、换行、排版和标注结构。验证通过后，再扩大文本池。

如果扩大到生产级，建议执行两个分支：

- 横排西里尔蒙古文：继续抓取 `mn.wikipedia.org`，目标 5,000-20,000 段清洗文本。
- 传统蒙古文：单独调研和采集传统蒙古文网页/教材/OCR 文本，目标先做 500-1,000 段人工抽检文本。
