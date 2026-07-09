# Chinese (SC) Font Source And License Notes

本目录用于 VL11 中文双语混杂渲染（少数民族语 + 中文并存版面）。

## Included Fonts

- `NotoSansSC-Regular.otf`
- `NotoSansSC-Bold.otf`

内部 family 名：`Noto Sans SC`。使用 noto-cjk 的 SubsetOTF/SC 版本，覆盖简体中文常用汉字。

## Rendering Use

- 中文块渲染栈优先 `Noto Sans SC`。
- 仅用于 mixed 文档中被选为中文的块；pure 文档不含中文。

## Source And License

- Noto Sans SC: https://fonts.google.com/noto/specimen/Noto+Sans+SC
- 源仓库：https://github.com/notofonts/noto-cjk （Sans/SubsetOTF/SC）
- SIL Open Font License: https://openfontlicense.org/
