# Tibetan Font Source And License Notes

本目录用于藏语合成 OCR 数据的本地渲染，补齐服务器可能缺失的藏文字体。

## Included Fonts

- `NotoSerifTibetan-Regular.ttf`
- `NotoSerifTibetan-Bold.ttf`

内部 family 名：`Noto Serif Tibetan`。

## Rendering Use

- 藏语 language profile 的 `font_family` 保留 macOS 侧字体名（`Qomolangma-Uchen Sarchung`、`Kailasa`）用于本地开发，并追加 `Noto Serif Tibetan` 作为跨平台回退。
- 在 Linux 服务器上，藏文字符最终由 `Noto Serif Tibetan` 或 fontconfig 的 serif 泛回退渲染。
- 不改变标签文本内容。

## Source And License

- Noto Serif Tibetan: https://fonts.google.com/noto/specimen/Noto+Serif+Tibetan
- 源仓库：https://github.com/notofonts/tibetan
- Noto license note: https://notofonts.github.io/noto-docs/website/use/
- SIL Open Font License: https://openfontlicense.org/
