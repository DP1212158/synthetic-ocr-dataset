# Korean (Hangul) Font Source And License Notes

本目录用于朝鲜语（谚文 Hangul）合成 OCR 数据的本地渲染，补齐服务器可能缺失的谚文字体。

## Included Fonts

- `NotoSansKR-Regular.otf`
- `NotoSansKR-Bold.otf`

内部 family 名：`Noto Sans KR`。使用 noto-cjk 的 SubsetOTF/KR 版本（谚文子集，单文件约 4.6MB），而非完整 CJK 或可变字体，便于控制仓库体积并保证 family 名稳定。

## Rendering Use

- 朝鲜语 language profile 的 `font_family` 保留 macOS 侧字体名（`Apple SD Gothic Neo`）用于本地开发，并追加 `Noto Sans KR` 作为跨平台回退。
- 在 Linux 服务器上，谚文字符最终由 `Noto Sans KR` 或 fontconfig 的 sans-serif 泛回退渲染。
- 不改变标签文本内容。

## Source And License

- Noto Sans KR: https://fonts.google.com/noto/specimen/Noto+Sans+KR
- 源仓库：https://github.com/notofonts/noto-cjk （Sans/SubsetOTF/KR）
- Noto CJK license note: https://github.com/notofonts/noto-cjk/blob/main/LICENSE
- SIL Open Font License: https://openfontlicense.org/
