# 阿舟来源库维护工具

在本机检查六个已登记的信源、归档选文、审核导出和备份。信源名称和入口来自[官网目录](../../site/library-content/sources.json)，采集规则保存在 [sources.json](sources.json)。正式选文由[官网](https://tefuirnever.github.io/azhou-ai-hub/zh/library/)提供搜索与 RSS。

## 试抓和登记

在本目录使用 Python 3.11.5 或更新版本和 uv。用仓库外的私有目录保存数据，或者在示例中替换目录路径。

```sh
uv sync --locked
uv run --locked python library.py preview openai
uv run --locked python library.py --data "$HOME/.local/share/azhou-source-library/catalog" sync openai
uv run --locked python library.py --data "$HOME/.local/share/azhou-source-library/catalog" status
```

`preview` 返回本次匹配数和最多 20 条元数据。手动运行 `sync` 后可查看「有更新」「无更新」或「抓取失败」。失败时保留上次成功时间，成功重试按文章身份去重。小米 MiMo 可用 `preview mimo --url <官方文章地址>` 检查单篇链接。

## 私有留存和备份

逐篇核对留存依据，再从浏览器另存作者发布的网页 HTML。导入会保存原始 HTML 与可读正文，并记录未随正文保留的媒体。

```sh
azhou_catalog="$HOME/.local/share/azhou-source-library/catalog"
uv run --locked python library.py --data "$azhou_catalog" archive openai \
  https://openai.com/index/how-openai-performance-factory-keeps-chatgpt-fast/ \
  --saved-html /path/to/saved-page.html --basis "本次留存依据"
uv run --locked python library.py --data "$azhou_catalog" list
uv run --locked python library.py --data "$azhou_catalog" backup /path/to/new-backup
```

`inspect <id>` 可读归档版本和正文。备份会校验私有数据库引用的文件。恢复时把整个备份复制到新的私有目录，再用 `list` 和 `inspect` 核对。

## 审核与发布

用 `review <id> link --basis "<发布依据>" --note "<自写导读>"` 登记链接审核。全文审核用 `review <id> full --revision <版本摘要> --basis "<发布依据>" --note "<自写导读>"`。用 `withdraw <id>` 从后续导出移除审核结果。

`export <新目录>` 生成一份仅含已审核条目的交接包。维护者再核对权利范围，把获准条目纳入[官网发布清单](../../site/library-content/first-edition.json)，由常规 PR 和 Pages 流程发布。线上下架同样通过修改官网发布清单并部署验证。

```sh
uv run --locked python -m unittest -v test_library
```
