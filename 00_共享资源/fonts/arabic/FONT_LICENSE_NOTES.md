# Arabic Font Source And License Notes

本目录用于维吾尔语、哈萨克语等 Arabic-script 合成 OCR 数据的本地渲染。

## Included Fonts

- `NotoNaskhArabic-Regular.ttf`
- `NotoNaskhArabic-Bold.ttf`
- `NotoSansArabic-Regular.ttf`
- `NotoSansArabic-Bold.ttf`
- `ScheherazadeNew-Regular.ttf`
- `ScheherazadeNew-Bold.ttf`

## Rendering Use

- 主体正文优先使用 `Local Noto Naskh Arabic`。
- 无衬线或备用场景使用 `Local Noto Sans Arabic`。
- 手写/信件类当前使用 `Local Scheherazade New` 作为更接近传统 Naskh 的替代字体。
- 不使用 Arabic Presentation Forms 转换，不插入 ZWJ/ZWNJ，不改变标签文本内容。

## Source And License

- Noto Naskh Arabic: https://fonts.google.com/noto/specimen/Noto+Naskh+Arabic
- Noto Sans Arabic: https://fonts.google.com/noto/specimen/Noto+Sans+Arabic
- Noto license note: https://notofonts.github.io/noto-docs/website/use/
- Scheherazade New: https://software.sil.org/scheherazade/
- SIL Open Font License: https://openfontlicense.org/

以上字体用于本地 HTML/Chromium 渲染链，依赖字体自身 OpenType Arabic shaping 特性和浏览器 shaping engine 实现连写。
