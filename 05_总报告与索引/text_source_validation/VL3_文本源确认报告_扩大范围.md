# VL3 文本源确认报告（扩大来源范围）

- 生成时间：2026-07-03T18:09:39
- 标准：不再限定必须是电子书；只要文本源可追溯、能读取/抽取、目标文字脚本比例达标、样本文本可读，即可用于 VL3 文本池。
- 验证方式：读取 EPUB/PDF/TXT/JSONL 候选源，按语种脚本正则统计可读段落和脚本比例。

| 语种 | 状态 | 来源类型/书目 | 可读段落 | 最高脚本比例 | 本地路径 |
|---|---|---|---:|---:|---|
| 壮语 | pass_small_public_text_source | zawiki-Vahcuengh-20200727.pdf / DjVuTXT | 9 | 0.948 | `05_总报告与索引/text_source_validation/cache/zhuang_archive_djvu_txt.txt` |
| 藏语 | pass | Kriya Tantra Leethong.epub | 4262 | 1.0 | `02_语种工程资源/藏语/01_文本数据获取/data/vl3_long_text_sources/source_files/Kriya Tantra Leethong.epub` |
| 蒙古语 | pass_verified_local_text_pool | existing verified traditional Mongolian text pool; ebook source not yet verified | 384 | 1.0 | `02_语种工程资源/蒙古语/01_文本数据获取/data/local_verified_label_text_pool_cleaned_20260702/records.jsonl` |
| 维吾尔语 | pass | مۇقەددەس يازمىلارنىڭ يېڭى دۇنيا تەرجىمىسى | 40 | 0.9773 | `05_总报告与索引/text_source_validation/cache/uyghur_jw_nwt_epub.epub` |
| 哈萨克语 | pass | كيەلى جازبالار. جاڭا دۇنيە اۋدارماسى | 2337 | 0.931 | `05_总报告与索引/text_source_validation/cache/kazakh_jw_nwt_epub.epub` |
| 朝鲜语 | pass | 신세계역 성경 (2014년 개정판) | 26483 | 1.0 | `05_总报告与索引/text_source_validation/cache/korean_jw_nwt_epub.epub` |
| 白语 | pass_verified_local_text_pool | 白语大理方言基础教程 / existing verified Bai text pool | 619 | 1.0 | `02_语种工程资源/白语/01_文本数据获取/data/local_verified_label_text_pool_20260702/records.jsonl` |

## 结论

- 7 个语种均已找到可读取、脚本比例达标、样本文本可读的文本来源。
- 白语和传统蒙古文采用 `verified_local_labels` 文本池作为扩大范围后的正式文本源；后续生成时应保留该 provenance，不标成 ebook。
- 壮语当前公共文本源偏短，但能抽取可读文本；如全量追求更强多样性，仍建议继续补更长壮语文本。

## 样本文本

### 壮语 - pass_small_public_text_source
- 来源：https://archive.org/download/zawiki-Vahcuengh-20200727.pdf/zawiki-Vahcuengh-20200727_djvu.txt
- SHA256：`6acddf3f8f15a075...`
- provenance_note：Expanded-scope text source. Readable Zhuang text extracted from Archive/Wikipedia PDF text; source is small but usable as a verified public text supplement.

```text
Sawcuengh dwg saw gyoebyaem, yung lahdingh cihmeh guh cihmeh hingzsik, yungh Vahcuengh fanghyenz haihbaek guh goekdaej, aeu yaem Vahcuengh Vujmingz guh biucinj, dwg yinzminz cwngfuj youg 1956 nienz caux ok, 1957 nienz ginggvaq bihcinj youq dieg Bouxcuengh doihengz sawjyungh cunj dahit saujsu minzcuz
```

```text
■ The prospects for the long-term survival of Non-Han minority languages in the south of China (http://www.linguapax.org/congres04/pdf/prosser.pdf)
```

### 藏语 - pass
- 来源：local file stored under Tibetan text source directory
- SHA256：`11a8a1a5d64f211d...`
- provenance_note：local supplied EPUB; license note not verified by script

```text
། སྐབས་དེར་དམིགས་པ་སྤོ་བ་ཙམ་ལས་མེ་ལྕེ་མི་དམིགས་པར་བསྒོམ་པའི་དོན་མིན་པར་འདོད་པ་ལྟར་ན་སྐབས་དེར་མེ་ལྕེ་ཡང་སྒྲུབ་པ་པོ་དེའི་དམིགས་པའི་ཡུལ་དུ་ཡོད་དགོས་པར་འདོད་དགོས་ཤི ང་། དེ་ལྟར་ན་སྒྲ་གནས་ཀྱི་སྐབས་སུ་སྒྲ་འབའ་ཞིག་ལ་དམིགས་པར་མི་འགྱུར་བའི་ཐལ་བ་ཡོད་ཅི ང་། མེ་གནས་དང་སྒྲ་གནས་གཉིས་ལ་དམིགས་པ་གཏད་ས་ཙམ་ལས་དམིགས་རྣམ
```

```text
། ལྷག་པར་ཨེ་ཝཾ་ཕྱག་རྒྱ་ལས་མི་བསྐྱོད་རྡོ་རྗེའི་མདོ་སྔགས་ཀྱི་ལྟ་བ་མཐར་ཐུག་པ་ཤ་སྟག་བསྟན་པ་ཞིག་ཡིན་པ་ད ང་། དཔལ་ཁང་ལོ་ཙཱ་བ་ད ང་། དཔའ་བོ་གཙུག་ལག་རྒྱ་མཚོ་ད ང་། འཇམ་མགོན་བློ་གྲོས་མཐའ་ཡས་སོགས་ཀྱིས་ཀྱང་མི་བསྐྱོད་རྡོ་རྗེའི་ལུགས་སུ་བྱ་རྒྱུད་ལ་ཙམ་ཁྱད་གཉིས་སུ་ཕྱེས་ནས་གསུངས་པས་ན་ཀརྨ་ཀམ་ཚང་ཡོངས་གྲགས་ལ་ཡང་མི་བསྐྱོད་
```

### 蒙古语 - pass_verified_local_text_pool
- 来源：local verified traditional Mongolian text pool
- SHA256：`1f71bd2d7ed63b78...`
- provenance_note：Expanded-scope text source. The cleaned local verified traditional Mongolian text pool is readable and script-valid; it is not a downloadable ebook, so keep provenance as verified_local_labels.

```text
ᠲᠡᠮᠦᠷ ᠠᠶᠠᠭ᠎ᠠ᠄ ᠲᠣᠳᠣᠳᠬᠠᠯ ᠲᠤᠳᠤᠳᠬᠠᠭᠠᠯᠤᠭᠴᠢ ᠶᠢᠨ ᠬᠠᠷᠢᠴᠠᠭ᠎ᠠ
```

```text
ᠵᠤᠤ ᠢᠤᠢ ᠬᠠᠢ᠂ ᠢᠯᠠᠯᠠᠲᠠ᠂ ᠪᠦᠷᠭᠦᠳ ᠪᠤᠳᠠᠭ᠎ᠠ ᠢᠳᠡᠬᠦ ᠪᠡᠷ ᠶᠠᠪᠤᠨ᠎ᠠ᠃ ᠵᠤᠤ ᠢᠤᠢ ᠬᠠᠢ ᠪᠤᠳᠠᠭ᠎ᠠ ᠢᠳᠡᠬᠦ ᠪᠡᠷ ᠲᠡᠮᠦᠷ ᠠᠶᠠᠭ᠎ᠠ᠂ ᠮᠣᠳᠣᠨ ᠰᠠᠪᠬ᠎ᠠ᠂ ᠮᠦᠩᠭᠦᠨ ᠬᠠᠯᠪᠠᠭ᠎ᠠ ᠠᠪᠴᠢᠷᠠᠪᠠ᠃
```

### 维吾尔语 - pass
- 来源：https://akamd1.jw-cdn.org/sg2/p/59fc07/1/o/nwt_UGA.epub
- SHA256：`5a434bf8f0f56259...`
- provenance_note：JW.org public EPUB; source/license terms must be reviewed before redistribution

```text
ئېلىنغان مە‌زمۇن كىتابلارنىڭ ناملىرى ۋە تىزىملىكى
```

```text
ئېلىنغان مە‌زمۇن مە‌تتا كىتابىنىڭ قىسقىچە مە‌زمۇ‌نى
```

### 哈萨克语 - pass
- 来源：https://akamd1.jw-cdn.org/sg2/p/5d36c60/2/o/nwt_AZA.epub
- SHA256：`61bcb5cd164d2f41...`
- provenance_note：JW.org public EPUB; source/license terms must be reviewed before redistribution

```text
‏الىنعان ءماتىن فىلىپىلىكتە‌رگە
```

```text
‏الىنعان ءماتىن فىلىپىلىكتە‌رگە
```

### 朝鲜语 - pass
- 来源：https://akamd1.jw-cdn.org/sg2/p/70b89ce/2/o/nwt_KO.epub
- SHA256：`faec4534e8f1c3e6...`
- provenance_note：JW.org public EPUB; source/license terms must be reviewed before redistribution

```text
북쪽 열 지파 이스라엘 왕국이 멸망되다 예언자 이사야 미가 스바냐 예레미야 나훔 하박국 다니엘 에스겔 오바댜 호세아
```

```text
바나바는 어떻게 사울이 길에서 주를 보았고 주께서 그에게 말씀하셨는지 그리고 어떻게 그가 다마스쿠스에서 예수의 이름으로 담대하게 말했는지를 그들에게 상세히 이야기해 주었다.
```

### 白语 - pass_verified_local_text_pool
- 来源：local verified label text pool; official related book page: https://cbs.muc.edu.cn/info/1223/4956.htm
- SHA256：`8aa759734f6696e1...`
- provenance_note：Expanded-scope text source. The local verified Bai text pool is readable and script-valid; it is not a downloadable ebook, so keep provenance as verified_local_labels.

```text
Dit Qi Zanx Daiblit Dit Yi Jif Yifbainx Guixdienb Dit Nei Jif Weittuf Daiblit Dit Sanl Jif Daiblit Tienpcel Dit Bia Zanx Miepsib Zefssenk
```

```text
belded sua ded sua nadzil sua gerlzil sua hhex sua belhhex sua zerdserx ni gerlni merlni atzip ni atwa ni atmerd ni
```