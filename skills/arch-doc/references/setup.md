# Setup（外部依赖）

本 skill 的默认检查全部使用 Python 3 标准库（argparse / re / pathlib / hashlib / subprocess），无第三方依赖、无网络访问。

## 可选依赖

| 依赖 | 用于 | 最低版本 | 缺失时的边界 |
|---|---|---|---|
| `plantuml`（本地 CLI，含 Graphviz） | `verify_doc.py --plantuml-cli` 逐图渲染门 | 任意能跑 `-failfast2 -tpng` 的发行版 | 未检测到时输出 `HINT ... skipped` 并跳过渲染门；配平/链接等其余检查照跑。不在无该依赖的机器上宣称「已验证可渲染」 |

检测命令：`command -v plantuml`。安装由用户自行选择（brew install plantuml / apt install plantuml）；本 skill 不代装、不改系统配置。
