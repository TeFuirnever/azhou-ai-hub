# 阿舟来源库维护工具

在本机检查六个已登记的信源、归档选文、审核导出和备份。信源名称和入口来自[官网目录](../../site/library-content/sources.json)，采集规则保存在 [sources.json](sources.json)。正式选文由[官网](https://tefuirnever.github.io/azhou-ai-hub/zh/library/)提供搜索与 RSS。

## 试抓和登记

在本目录使用 Python 3.11.5 或更新版本和 uv。以下采集与归档命令由维护者手动触发。用仓库外的私有目录保存数据，或者在示例中替换目录路径。

```sh
uv sync --locked
uv run --locked python library.py preview openai
uv run --locked python library.py --data "$HOME/.local/share/azhou-source-library/catalog" sync openai
uv run --locked python library.py --data "$HOME/.local/share/azhou-source-library/catalog" status
```

`preview` 返回本次匹配数和最多 20 条元数据，不写入目录或信源状态。`sync` 只登记候选文章及采集状态，正文由后续 `archive` 导入。状态分为「有更新」「无更新」和「抓取失败」。失败时保留上次成功时间，成功重试按文章身份去重。`sync all` 检查五个可从 RSS 或网页列表发现文章的来源。小米 MiMo 需提供官方文章地址，用 `preview mimo --url <地址>` 试抓，或用 `sync mimo --url <地址>` 登记。

RSS 和网页列表遇到短暂网络故障或部分上游服务器错误时，在同一次命令内最多重试一次。若服务器给了 `Retry-After` 或解析未匹配，按本次抓取失败处理。[上游源码及引入记录](../../THIRD_PARTY_NOTICES.md#aihot-source-listing-retry)

## 私有留存和备份

逐篇核对留存依据，再用 `--fetch-original` 从已登记的官方页面抓取原始 HTML 和可读正文。也可以用 `--saved-html <文件>` 导入浏览器另存的网页。默认只留存页面和正文，外部媒体缺项会记在对应版本。若留存依据覆盖图片，可以在联网抓取时加 `--include-images`，命令会从信源允许的主机下载支持的图片。

```sh
azhou_catalog="$HOME/.local/share/azhou-source-library/catalog"
uv run --locked python library.py --data "$azhou_catalog" archive openai \
  https://openai.com/index/how-openai-performance-factory-keeps-chatgpt-fast/ \
  --saved-html /path/to/saved-page.html --basis "本次留存依据"
uv run --locked python library.py --data "$azhou_catalog" list
uv run --locked python library.py --data "$azhou_catalog" backup /path/to/new-backup
```

要直接抓取，替换命令中的 `--saved-html /path/to/saved-page.html` 为 `--fetch-original`。同一篇文章重跑时沿用条目 ID，内容或媒体变化会另存版本。归档后的正文仍需另行审核才可进入发布交接包。

`inspect <id>` 可读最近一次归档的版本和正文，传入 `--revision` 可查看指定版本。备份会校验私有数据库引用的文件。恢复时把整个备份复制到新的私有目录，再用 `list` 和 `inspect` 核对。

## 审核与发布

用 `review <id> link --basis "<发布依据>" --note "<自写导读>"` 登记链接审核。全文审核用 `review <id> full --revision <版本摘要> --basis "<发布依据>" --note "<自写导读>"`。用 `withdraw <id>` 从后续导出移除审核结果。

旧版归档可继续查看。若旧版归档缺少对应版本的标题和作者等记录，重新导入当时保存的网页，再按新版本摘要审核全文。

`export <新目录>` 生成一份仅含已审核条目的交接包，供维护者核对和转录。上线时由维护者更新[官网发布清单](../../site/library-content/first-edition.json)和获准公开的正文文件，经常规 PR 和 Pages 流程发布。当前官网构建只接受注明 CC0 1.0 且通过校验的全文文件。首发授权与正文范围见[选文说明](../../site/library-content/NOTICE.md)。

官网的双语页面、搜索和 [RSS](https://tefuirnever.github.io/azhou-ai-hub/library/rss.xml) 使用同一份已批准的清单。撤回线上条目时更新清单并部署，再核对条目页、搜索和 RSS。

```sh
uv run --locked python -m unittest -v test_library
```
