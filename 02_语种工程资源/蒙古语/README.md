# 传统蒙古文

本目录现在只保留服务器重新生成所需的语种源资产，不保留历史生成图片、HTML、标签和 QA 输出。

- language id: `mongolian`
- 文字方向：传统蒙古文，竖排 vertical-lr
- 当前文本池：`01_文本数据获取/data/vl3_long_text_sources/records.jsonl`
- 语言 profile：`03_合成数据生成/configs/mongolian_language_profile.json`
- 通用生成脚本：`../../03_通用生成pipeline/多语种合成数据生成/scripts/run_full_generation.py`

蒙古语还保留 `03_合成数据生成/configs/mongolian_vertical_templates_v3/` 和 `mongolian_vertical_templates_v4/`，用于后续竖排专项修复。

生成数据时不要在本目录手动复制通用脚本或通用模板；统一使用 `03_通用生成pipeline/` 下的主线入口。
