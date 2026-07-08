# Mongolian Font Source And License Notes

本目录用于传统蒙古文合成 OCR 数据的本地渲染，补齐服务器可能缺失的传统蒙古文字体。

## Included Fonts

- `NotoSansMongolian-Regular.ttf`

内部 family 名：`Noto Sans Mongolian`。

## Rendering Use

- 蒙古语 language profile 的 `font_family` 首选即为 `Noto Sans Mongolian`，与本文件一致。
- 传统蒙古文为竖排 `vertical-lr`，字体本身需支持竖排 shaping；渲染后必须人工视觉抽检，不能只看自动 QA。
- 不改变标签文本内容。

## Source And License

- Noto Sans Mongolian: https://fonts.google.com/noto/specimen/Noto+Sans+Mongolian
- 源仓库：https://github.com/notofonts/mongolian
- Noto license note: https://notofonts.github.io/noto-docs/website/use/
- SIL Open Font License: https://openfontlicense.org/
