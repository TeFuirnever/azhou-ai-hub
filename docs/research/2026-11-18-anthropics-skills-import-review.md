# anthropics/skills 文档品类引入 · 法务核查与采源冻结 — 2026-11-18

本记录是只读采源核查与冻结（沿 [`docs/research/2026-11-11-pstack-upstream-gap.md`](2026-11-11-pstack-upstream-gap.md) 的先例）：未采用任何技能、未改动任何包、未新增任何支持声明；不触碰 pstack 排除范围。全部结论钉住 2026-11-18 的实测；本单元为 docskills-U0（差距补齐路线图首个单元），交付物是 §7 的三项维护者裁决与本文的冻结摘要。

## 1. 审计来源身份

| 项 | 值 |
|---|---|
| 仓库 | [anthropics/skills](https://github.com/anthropics/skills) |
| 不可变 commit | `e4bb5d960d87126ff3b3a8af1a104b7db67560ba` |
| author date | 2026-11-16T14:22:47Z |
| message | Update docx, pptx and xlsx skills: zipfile unpack, zip -y, validate.py and soffice.py fixes (#2221) |
| tree | `d495c40fdd16cfe817a71aa05ecc1969ba98e925`（544 entries，`truncated:false`） |

解析命令见 §8 V0，2026-11-18 复跑回执与上表一致。

## 2. 许可核查

- 仓库级 license 字段为空：`gh api repos/anthropics/skills --jq .license` 返回 `null`（2026-11-18 实测）。
- [README（钉 commit）](https://github.com/anthropics/skills/blob/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/README.md) L20 原文：文档四技能「These are also open source (Apache 2.0)」，且上游自证其驱动 Claude 生产文档能力（链接指向 anthropic.com/news/create-files）。
- 六个候选包各带 `LICENSE.txt`，全文为 Apache-2.0 标准文本，实测恰两份字节变体（SHA-256）：
  - docx = pdf = pptx = xlsx = `58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd`
  - mcp-builder = webapp-testing = `bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362`
  - `diff` 实测唯一差异 `190c190`：`Copyright [yyyy] [name of copyright owner]`（占位模板行，四文档包）↔ `Copyright 2026 Anthropic, PBC.`（具名行，两工具包）。
- 上游 `SKILL.md` frontmatter 携带宿主专用 `license: Complete terms in LICENSE.txt` 键（pdf 与 mcp-builder 实测同款）；按 super-gh-axi 先例，采用时该键翻成中性 frontmatter 并丢弃。
- **维护者裁决 R1（Apache-2.0 §4(a) 归属）：接受引入**。理由与条件见 §7。

## 3. 第三方组件映射

上游 [`THIRD_PARTY_NOTICES.md`](https://github.com/anthropics/skills/blob/e4bb5d960d87126ff3b3a8af1a104b7db67560ba/THIRD_PARTY_NOTICES.md) 组件清单（实测摘录）：imageio 2.37.0（BSD-2-Clause）、imageio-ffmpeg 0.6.0（BSD-2-Clause）、FFmpeg 7.0.2（GPL-3.0）、Pillow（HPND/MIT-CMU 系）及 OFL 字体条目。

候选六子树全量字节扫描（101 条唯一路径 = 201 blob，office/ 50 blob 三包重复计一份，2026-11-18 逐文件抓取实测）：

- `ffmpeg` / `imageio` 小写子串：**0 命中**。GPL-3.0 FFmpeg 与 BSD imageio/imageio-ffmpeg 不随本仓 vendored 字节进入。
- 字体文件（`.ttf/.otf/.woff/.woff2`）：候选子树内 **0 个**（全树另有 54 个，均在候选范围之外）。OFL 组件不随 vendored 字节进入。

第三方运行时依赖（import 全量扫描；口径修订 2026-11-18：初版「211 条 import 行」实为 36 个唯一 .py/.js（58 个文件面，office/ 三包重复）的顶格 `import`/`from` 正则计数，对缩进 import 与 CommonJS `require()` 不可见；本版扩为全语句口径，复算 Python AST import 语句 240 条 + `apply_theme.js` 的 `require()` 代码 2 条）：

| 组件 | 出现位置 | 结论 |
|---|---|---|
| pypdf | pdf/scripts/ 四脚本 | 运行时外部依赖，U1（pdf）setup 合同承接 |
| pdf2image | pdf/scripts/convert_pdf_to_images.py | U1（pdf）承接 |
| pdfplumber | pdf/scripts/extract_form_structure.py | U1（pdf）承接；差距设计抽查清单未含，本单元实测新增 |
| PIL (Pillow) | pdf/scripts/create_validation_image.py、pptx/scripts/thumbnail.py | U1（pdf）与 U4（pptx）两侧承接 |
| defusedxml | office/ 六脚本（validators/base、docx、redlining、soffice、validate、helpers/pptx_chart）、docx/scripts/comment.py、merge_runs.py、pptx/scripts/add_slide.py、clean.py、thumbnail.py、xlsx/scripts/recalc.py（:293、:353） | U2–U4 承接（office/ 共享子树与各包脚本均消费） |
| lxml.etree | office/validators/base.py、docx.py、pptx.py（8 处缩进 import） | U2–U4 共享 office 子树承接；差距设计抽查清单未含，本单元实测新增 |
| python-pptx (`pptx.package`) | pptx/scripts/slide_text.py | U4（pptx）承接 |
| openpyxl | xlsx/scripts/recalc.py:418–419（缩进 import；`_scan_xml` 异常时 `_report` 回落 `_scan_with_openpyxl`，:458–462） | U3（xlsx）承接；初版扫描漏项，本版复算补录 |
| pptxgenjs、jszip（Node） | pptx/scripts/apply_theme.js:29（jszip 经 pptxgenjs 解析路径加载，缺失即 throw） | U4（pptx）承接；初版扫描漏项，本版复算补录 |
| anthropic、mcp | mcp-builder/scripts/evaluation.py、connections.py | 运行时外部依赖（R3 暂缓，不排期） |
| playwright.sync_api | webapp-testing/examples/ 三个示例脚本 | 运行时外部依赖（R3 暂缓，不排期）；`scripts/with_server.py` 仅 stdlib，实测无 playwright |

office/ 子树的 import 扫描以 docx 名下副本为源；pptx/xlsx 副本经 git blob SHA 相等证明字节一致（§5），import 面随字节相等而覆盖。

## 4. 候选冻结摘要（逐技能）

| 子树 | blob 数 | 字节数 (B) |
|---|---|---|
| skills/pdf | 12 | 68,603 |
| skills/docx | 61 | 1,166,158 |
| skills/pptx | 58 | 1,199,661 |
| skills/xlsx | 53 | 1,164,621 |
| skills/mcp-builder | 11 | 159,159 |
| skills/webapp-testing | 6 | 22,394 |
| 合计 | 201 | 3,780,596 |

口径注记：差距设计原文的 13/72/68/63/13/8 是含目录条目的 tree entry 数；本记录与后续 vendor manifest 一律以 **blob 数**为准（字节数两侧一致）。附录 A 收 101 条唯一路径（office/ 50 blob 计一份并标注三包共享）。

## 5. office/ 共享子树权威副本规则

- 实际路径为 `skills/<pkg>/scripts/office/`（docx/pptx/xlsx 三包各含一份）。执行纠正：差距补齐草案与路线图按 `skills/<pkg>/office/` 表述，本单元复跑时发现并更正；`git/trees` API 按 `scripts/office/` 前缀匹配。
- 三份副本各 50 blob，逐路径 git blob SHA 三方完全相等（实测 OFFICE-PARITY-OK；git blob SHA 相等即内容字节相等），单份 50 blob 合计 1,109,154 B（三份副本合计 3,327,462 B）。
- 本仓采用「逐包 byte-identical 副本」以满足 skill-standard §2 的独立安装（包不依赖兄弟目录）；U2–U4 的 parity 测试以本节与附录 A 的 office/ 段为对照源。

## 6. 采源范围与排除声明

- 排除（不进入任何后续采用单元的 sourcing 范围）：上游 `.claude-plugin/`、`spec/`、`template/`、`.gitignore`，以及 13 个非候选技能：academy-guide、algorithmic-art、brand-guidelines、canvas-design、claude-api、discernment-nudge、doc-coauthoring、frontend-design、internal-comms、skill-creator、slack-gif-creator、theme-factory、web-artifacts-builder（顶级条目与技能全集均 tree API 实测枚举，共 19 个技能）。
- pstack 排除范围不受影响：本单元零字节改动，未触碰 `packages/` 下任何路径。

## 7. 维护者裁决区（本单元交付物）

三项裁决均于 2026-11-18 落定。裁决方式：维护者在路线图批准对话中授权代理会话按其默认判断落地（「听你的」），本记录如实标注该授权来源；任何一项均可在后续评审中推翻并回到 pending。

- **R1 Apache-2.0 §4(a) 归属：接受**。上游 README L20 明文 Apache-2.0 授权声明 + 仓库身份 Anthropic PBC + 逐包 LICENSE.txt 全文副本，授权意图无歧义；附录版权行的占位形态是上游自身瑕疵，按字节原样保留即履行 §4(a)，不代填。三个强制条件随采用单元生效：
  1. LICENSE.txt 逐包字节原样复制，保留占位版权行；
  2. 本仓 THIRD_PARTY_NOTICES 在各采用 PR 中具名「Anthropic PBC, from anthropics/skills @ e4bb5d960d…, Apache-2.0」；
  3. 占位行异常写入各包 provenance；若上游后续补正版权行，按 skill-standard §1.2 稳定源规则重新裁决同步。
- **R2 格式集与顺序：全套按序引入**。pdf → docx → xlsx → pptx（路线图 docskills-U1→U4 原序），理由：文档工作流四格式互补，逐包原子 PR 已有既定切分。
- **R3 mcp-builder / webapp-testing：本轮暂缓**。需求侧证据弱（anthropics #675 仅 2 反应）；webapp-testing 与既有 archify browser-check、lavish 循环、record-browser-gif 能力面重叠。待真实任务拉动后再立项，暂不排期。

## 8. 可复跑核验命令（2026-11-18 实测输出摘录）

- V0 提交解析：`gh api repos/anthropics/skills/git/commits/e4bb5d960d87126ff3b3a8af1a104b7db67560ba` → §1 表四值。
- V1 license 变体：六包各 `curl -fsSL https://raw.githubusercontent.com/anthropics/skills/<commit>/skills/<pkg>/LICENSE.txt | shasum -a 256` → §2 两值，四文档包与两工具包各自成组。
- V2 变体 diff：两份 LICENSE.txt `diff` → 唯一 hunk `190c190`（占位行 ↔ 具名 Anthropic PBC）。
- V3 树对照：`gh api "repos/anthropics/skills/git/trees/<commit>?recursive=1"` → 544 entries、`truncated:false`；复算 §4 计数、§5 parity、§6 枚举；office/ 前缀须用 `scripts/office/`。
- V4 附录 A：101 条唯一路径逐个 `curl -fsSL <raw URL> | shasum -a 256`，抓取 101/101 成功、0 失败；同一循环内完成 §3 的子串扫描与 import 扫描。
- V5 仓库门：`python3 scripts/verify.py`（含 markdown 链接门与 whitespace 门），见 PR 描述的运行记录。
- 冻结纪律：V5 前后各记 `git rev-parse HEAD`，期间无并发写（本单元在 Treehouse 租约 worktree `codex/docskills-u0` 上执行）。

## 9. 对后续采用单元的输出契约

- vendor manifest 钉值来源 = 附录 A（101 条唯一路径；office/ 段标注三包共享，U2–U4 复用）。
- setup 依赖合同输入（import 扫描口径，非完整清单；完整运行时依赖以各采用包上游 SKILL.md 的依赖声明与脚本实际消费交叉判定，SKILL.md 字节已钉附录 A；pdf 无独立 Dependencies 节、声明散见 Python Libraries/Command-Line Tools/Common Tasks 节，docx/pptx/xlsx 的 Dependencies 节亦可能漏列脚本侧 import）：pdf（pypdf、pdf2image、pdfplumber、Pillow）；office 家族（defusedxml、lxml，及各格式自身运行时：LibreOffice soffice、python-pptx、openpyxl、Node 侧 pptxgenjs/jszip 等）；mcp-builder（anthropic>=0.39.0、mcp>=1.1.0，暂缓不排期）；webapp-testing（Playwright，落在 examples，暂缓不排期）。本次复核补记非 import 口径的已知运行时项：docx 侧 npm `docx`、pandoc、pdftoppm/Poppler；pptx 侧 Poppler 与 react-icons、react、react-dom、sharp；xlsx 侧 pandas、markitdown；pdf 侧 pytesseract、reportlab、poppler 工具（pdftotext/pdfimages）、qpdf、pdftk（上游标注 if available）；Pillow 同属 pdf 与 pptx 两侧（pptx/scripts/thumbnail.py:30 顶层 import）。
- fidelity 分类预登记 `faithful`（skill-standard §2.3：能力原样保留，本地层仅包装中性 frontmatter 与 fail-closed setup）；「preinstalled 依赖 → fail-closed setup」的逐条 delta 在各采用 PR 的 provenance 终判。
- R1–R3 是各采用 PR 的前置引证；本记录是唯一裁决载体。

## 附录 A. 逐文件 SHA-256

101 条唯一路径（`路径  SHA-256`）。`skills/docx/scripts/office/` 下 50 条为三包共享（docx/pptx/xlsx 字节相同，见 §5）；其余 51 条为单包独有。本节由 V4 命令批量生成，是 U1–U4 vendor manifest 的唯一钉值来源。

```
skills/docx/LICENSE.txt  58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd
skills/docx/SKILL.md  895d5aa6c4cd98e4aed4c995d846f056f3549086e79bcd6617afea6014f82288
skills/docx/scripts/__init__.py  01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b
skills/docx/scripts/accept_changes.py  0c991d2bc7304a1248e9f3bf9b1498f0b6e76641fc457e7cbd73c99b4eef3a74
skills/docx/scripts/comment.py  37d116e5f56bb142b208c6c6a4bbcf960495abf470ddb7c6675ccfac864ba3d7
skills/docx/scripts/merge_runs.py  3ab367fd7fba4647943d0aa5e65203b15458551410f5ffc821d902616a4b9f40
skills/docx/scripts/office/helpers/__init__.py  5c456ffc522900399b5f9402f92d66aaf2d9f87655d236c69f60bf07f4fd7c9b  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/helpers/pptx_chart.py  aed734e9a6c743ae712fc228c868bf0f6abcfb6a53549eefb19081b15d240fda  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/helpers/pptx_slide.py  06fe06953bf038826b85ecc142f4dc9299a37fa0c4e4dd9b00b10486df33524d  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/helpers/pptx_theme.py  ebb54c56e9c13807f5f98f0cae22d47cdd0162da8525eaa664e3f2c8c8d6bb03  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/dml-chart.xsd  41b93bd8857cc68b1e43be2806a872d736a9bdd6566900062d8fdb57d7bbb354  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/dml-chartDrawing.xsd  3fd0586f2637b98bb9886f0e0b67d89e1cc987c2d158cc7deb5f5b9890ced412  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/dml-diagram.xsd  29b254ee0d10414a8504b5a08149c7baec35a60d5ff607d6b3f492aa36815f40  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/dml-lockedCanvas.xsd  5cb76dabd8b97d1e9308a1700b90c20139be4d50792d21a7f09789f5cccd6026  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/dml-main.xsd  5375417f0f5394b8dd1a7035b9679151f19a6b65df309dec10cfb4a420cb00e9  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/dml-picture.xsd  5d389d42befbebd91945d620242347caecd3367f9a3a7cf8d97949507ae1f53c  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/dml-spreadsheetDrawing.xsd  b4532b6d258832953fbb3ee4c711f4fe25d3faf46a10644b2505f17010d01e88  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/dml-wordprocessingDrawing.xsd  bdad416b096b61d37b71603b2c949484f9070c830bdaeba93bf35e15c8900614  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/pml.xsd  d173c3e5d61e42e2e3a97226c632fd2ab7cc481fc4e492365b87024ab546daff  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-additionalCharacteristics.xsd  3c6709101c6aaa82888df5d8795c33f9e857196790eb320d9194e64be2b6bdd8  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-bibliography.xsd  0b364451dc36a48dd6dae0f3b6ada05fd9b71e5208211f8ee5537d7e51a587e2  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-commonSimpleTypes.xsd  e2abacbb9a55ce1365f8961bc1b1395bbc811e512b111000d8c333f98458dece  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-customXmlDataProperties.xsd  0ef4bb354ff44b923564c4ddbdda5987919d220225129ec94614a618ceafc281  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-customXmlSchemaProperties.xsd  0d103b99a4a8652f8871552a69d42d2a3760ac6a5e3ef02d979c4273257ff6a4  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-documentPropertiesCustom.xsd  9c085407751b9061c1f996f6c39ce58451be22a8d334f09175f0e89e42736285  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-documentPropertiesExtended.xsd  bc92e36ccd233722d4c5869bec71ddc7b12e2df56059942cce5a39065cc9c368  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-documentPropertiesVariantTypes.xsd  7b5b7413e2c895b1e148e82e292a117d53c7ec65b0696c992edca57b61b4a74b  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-math.xsd  3213ef1631606250f5010b42cad7ef716f7c59426367798e33c374c0ec391d3a  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/shared-relationshipReference.xsd  12264f3c03d738311cd9237d212f1c07479e70f0cbe1ae725d29b36539aef637  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/sml.xsd  beffeed56945c22a77440122c8bdc426f3fcbe7f3b12ea0976c770d1f8d54578  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/vml-main.xsd  f5ee623b08b6a66935e5aced2f5d8ad0fc71bf9e8e833cd490150c0fa94b8763  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/vml-officeDrawing.xsd  585bedc1313b40888dcc544cb74cd939a105ee674f3b1d3aa1cc6d34f70ff155  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/vml-presentationDrawing.xsd  133c9f64a5c5d573b78d0a474122b22506d8eadb5e063f67cdbbb8fa2f161d0e  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/vml-spreadsheetDrawing.xsd  6bdeb169c3717eb01108853bd9fc5a3750fb1fa5b82abbdd854d49855a40f519  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/vml-wordprocessingDrawing.xsd  475dcae1e7d1ea46232db6f8481040c15e53a52a3c256831d3df204212b0e831  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/wml.xsd  c2dd9f61f892deae6acd8d20771ea79b12018af25f3bf8d06639c8542d218cfd  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ISO-IEC29500-4_2016/xml.xsd  a539aa2fb154fa50e0f5cc97e6ad7cbc66f8ec3e3746f61ec6a8b0d5d15ecdf2  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ecma/fouth-edition/opc-contentTypes.xsd  9e0b7209fc69ab11987900404540969976000c5ebe4d4f58c43dc3842886bf3a  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ecma/fouth-edition/opc-coreProperties.xsd  451958454e8588dfc7cd945981ada142ca06ff3307937f5700df059c2b307fa8  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ecma/fouth-edition/opc-digSig.xsd  6de111e11403f7cd49027400755bae0ea1cabef2815f09bd40a24f0017613b24  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/ecma/fouth-edition/opc-relationships.xsd  f565adfef5a502044abc3a9153e157edc25af78304d335994afb958874b15e26  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/mce/mc.xsd  3a37e461ecf5a8670fdec34029703401f8728ab9c96ec1739a6ae58d55212413  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/microsoft/wml-2010.xsd  568b26ee156cb9549aa439ca2158965f77b7c1602b7e0316f40ac6cf586e35f2  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/microsoft/wml-2012.xsd  0fa75578a000439a7988ba0c59fdc69f774bbd416cbacc14d07125b3f686cb74  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/microsoft/wml-2018.xsd  be0ff793a22dd31384650c3a4da14c2fa8062751c2e97b0e5ee852bda13c60ad  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/microsoft/wml-cex-2018.xsd  fddc2b880cabb9005aebbc7e783e53c19fec1c03df7d0e2f2076a33a0fdfd081  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/microsoft/wml-cid-2016.xsd  127ca209fa73d7cb708449cb355c871867948a96e4a74f7bf5811ef62d17991d  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/microsoft/wml-sdtdatahash-2020.xsd  842e7163409c8d74f4d7088a8bc99500d80bc75332681a0980055b08f374a604  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/schemas/microsoft/wml-symex-2015.xsd  16f6f8072249f431370723c2cd8974672e0d9c897e00e97dd918079df934871b  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/soffice.py  bcfa227707681ffbecc0f0af5c4e7155407b3baaf5cec5cdd41387c97cdd40c7  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/validate.py  8c10ec61d8e880877515019e1fe8fab9a1f590c9e50ed0631418e960aca1e313  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/validators/__init__.py  83e0f035c5abea238d3f2c3968afbd511ed022b527b7c9cb60a9434cc34ff987  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/validators/base.py  6129ec6a4fc0a4aa78af1434f9baa73994cc24d3261afda4e680e00f215cbf3b  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/validators/docx.py  7b0f1a23c9cd9ff07187d9d7d359f62317f94a5e389d63fd19766e1688a195a2  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/validators/pptx.py  3a100ec5f00ae183bca67f4aaa8e3e902caee60254e141b8120f32c53d85cee7  ; shared: docx/pptx/xlsx
skills/docx/scripts/office/validators/redlining.py  f9c4455adc32b3890d5203d6c25d868d98d7e970bbad76b686f502950737599a  ; shared: docx/pptx/xlsx
skills/docx/scripts/templates/comments.xml  a08ba83ee8790ac9e3dc61921f4988f19edd7e06ac09d6f1897a877c1581818d
skills/docx/scripts/templates/commentsExtended.xml  544eeecfeceed4b468fff163cd9c366d33641c8b8ab691ce002576197846afe8
skills/docx/scripts/templates/commentsExtensible.xml  bad10b3283e6ad6e7ef6d1ca5169683721ed690ee331282c65df04017e080631
skills/docx/scripts/templates/commentsIds.xml  db20f9616e004ec42ef736e80c2384e45db0f8d1194d31dc8b37c7d6ecdd6420
skills/docx/scripts/templates/people.xml  056f63aa1197fd8c9dda980c9f1b9ff016fd5fa4a462df8aec5f384f39d23e37
skills/mcp-builder/LICENSE.txt  bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362
skills/mcp-builder/SKILL.md  b483b56d6673134497e45489c317f26ae0f1429c194db0297e43073e17e6748c
skills/mcp-builder/reference/evaluation.md  8c99479f8a2d22a636c38e274537aac3610879e26f34e0709825077c4576f427
skills/mcp-builder/reference/mcp_best_practices.md  80fb4369a349447cf18ecdd7494fe7938b6065377e9f08c077cec411093a3007
skills/mcp-builder/reference/node_mcp_server.md  ee3c95d812e450f6168b734390d0c9ef6f8ebeef041d73a122c972dfbd4d476a
skills/mcp-builder/reference/node_mcp_server_v2.md  49b2fe48f33910b743ae3a56353fffa5d5f252f531053f24f2da4e5914c0d3aa
skills/mcp-builder/reference/python_mcp_server.md  2da52f77e675191014ca2e146a4b95aa04d0ca7dd7e2b100322df15ade685e80
skills/mcp-builder/scripts/connections.py  9403668a2041568772082a8b334122c1f88daf0541fb393af4522d0094a47a6e
skills/mcp-builder/scripts/evaluation.py  49ed1d17cdce5da101b210197740713f49b935c29d4f339542a14b132658e6f7
skills/mcp-builder/scripts/example_evaluation.xml  9272b348ddcc4b06ba562367ccd0770e018158c0068ac5116d5e34aaeff8777a
skills/mcp-builder/scripts/requirements.txt  d5d7558b2368ecea9dfeed7d1fbc71ee9e0750bebd1282faa527d528a344c3c7
skills/pdf/FORMS.md  d5df5757e23634cd8a1a37e092af6c3b3b63afb3fd3ce86337fce9017cc3ee9f
skills/pdf/LICENSE.txt  58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd
skills/pdf/REFERENCE.md  07af9a8f59e77e88fe9b238a403348244f38a4771c54911c412716d8f88f0ea9
skills/pdf/SKILL.md  d1c7caf5f35eb7d37877dd7fc33a095037be2b34fb5d2f7f4d43bde3165bb4ee
skills/pdf/scripts/check_bounding_boxes.py  0ced522402dd7b3c82a0be9518cf4e485fa9cc0467d7beab6ddb04cb36fcc3e1
skills/pdf/scripts/check_fillable_fields.py  1fe10b9980a5493c9bbec8c20630c603eaa475b45403751c08f26738736647b8
skills/pdf/scripts/convert_pdf_to_images.py  7f58e292a67e18a8ff000d30bad2469389546731f7e8a698cc1d0aed001ea15d
skills/pdf/scripts/create_validation_image.py  8fa9fd7962c9f940045b81cf6b991e7c1057c1838e3f9cc6d305007a222ffebf
skills/pdf/scripts/extract_form_field_info.py  bb235b36f497bbb1c7c6821cecf527bbba7213520de11219da99f7b13a38c109
skills/pdf/scripts/extract_form_structure.py  6814e3fe8f78c2b16d766c132b5a727ff7a31b71d76a7d46bd6e40fe50bc97c5
skills/pdf/scripts/fill_fillable_fields.py  d140872c2e92e41b1e05370ae8d270c5b7f5ebdf55d9905f03bc974a9c708ff5
skills/pdf/scripts/fill_pdf_form_with_annotations.py  8a56e063a49ed53c0b0e1d312ecf8023af76816ed139486ec3b539873de202fd
skills/pptx/LICENSE.txt  58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd
skills/pptx/SKILL.md  598c981d93f2173b251f86a4bc94e9fb4e4f5ddaa314ba2dd4eca24b7a07808e
skills/pptx/scripts/__init__.py  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
skills/pptx/scripts/add_slide.py  23a4c66a9f43e651189cbc9f82ba0a8271d19dc8d44cf0c426dda66f7eb6a93a
skills/pptx/scripts/apply_theme.js  e440b33c43f2e707076cb64b57ca926ce886564b115c19ee23ac487bdb1a6259
skills/pptx/scripts/clean.py  5c808cd4dff7e02661ef3c68b5917f4e25097cc6610c92a3a7df4a6366a5c3c1
skills/pptx/scripts/slide_text.py  0deab09d4ae494411ee893f9c69fffc19fe264a6053990a2f066334c0d88d422
skills/pptx/scripts/thumbnail.py  94ef83a84346aa2d63913de0d42bb2fe902ccdc17bfac6130096ca758381793c
skills/webapp-testing/LICENSE.txt  bc6b3af2f331cbc7fb0da1344efb2cbe5877a31498b4d70dbc7000f3405a1362
skills/webapp-testing/SKILL.md  51b7349e77ec63b7744a6f63647e7566a0b4d2e301121cc10e8c2113af6556a2
skills/webapp-testing/examples/console_logging.py  ea46877289acb82da7e7ce59d0bc37c8977cd57e2a006d0c88d7a1c625bf95da
skills/webapp-testing/examples/element_discovery.py  d63c89604a22f8845d724e95dda45db49b1bf57c25ce0a83afbb7b8da3d402f0
skills/webapp-testing/examples/static_html_automation.py  9d533aafb875ee3ab8b8ebf8f5b9003ac8d999da3d09b285cce252e623140064
skills/webapp-testing/scripts/with_server.py  b0dcf4918935b795f4eda9821579b9902119235ff4447f687a30286e7d0925fd
skills/xlsx/LICENSE.txt  58d1e17ffe5109a7ae296caafcadfdbe6a7d176f0bc4ab01e12a689b0499d8bd
skills/xlsx/SKILL.md  f32b1c2b5d5d31e02964df110d6489613d9345f86830c118cfe24159d8448ce6
skills/xlsx/scripts/recalc.py  7265aa4a41f5273596ee5694ce8a4d881c18adafb6203fece769107d08403263
```
