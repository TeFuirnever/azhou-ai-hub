# Azhou Agent Workbench · 阿舟 Agent 工作台

Azhou AI Hub 的 Agent 状态透视模块。当前版本提供 Performance，展示各宿主的原生会话性能。两个宿主的插件 ID 均为 `azhou-agent-inspector`，运行时由各自的插件管理器负责。市场目录使用本包的绝对路径。

| 宿主 | 安装 | 使用 |
|---|---|---|
| Codex Desktop | `codex plugin marketplace add /absolute/path/to/azhou-ai-hub/packages/azhou-agent-inspector`，再运行 `codex plugin add azhou-agent-inspector@azhou-agent-tools` | 在会话中调用阿舟 Agent 工作台读取统计。若回复中出现可展开的面板卡片，可从卡片打开侧栏。需要 Python 3 和本地 rollout 记录。 |
| ZCode Desktop 3.18.2+ | 在 ZCode 运行 `/plugin marketplace add /absolute/path/to/azhou-ai-hub/packages/azhou-agent-inspector`，再运行 `/plugin install azhou-agent-inspector@azhou-agent-tools` | 输入框底部显示生成速率，点击打开会话仪表盘。辅助命令包括 `/tps`。需要 Node.js。 |

Codex 侧栏与 ZCode 的仪表盘使用相同的阿舟头像、工作室壁纸和深浅两套配色。两边都把整轮耗时和速率放在主指标区。ZCode 在输入框底部提供速率入口，并展示会话统计和生成速率曲线。切到要查看的会话，再点该会话输入框的速率。仪表盘在会话标题下显示完整工作目录，窄栏里会换行。

在两个面板中都可以展开「性能详情」。在 Codex 也可以悬停该按钮，在 ZCode 也可以悬停输入框底部的速率。Codex 的 Context 占用来自最近一次有数据的请求和它的窗口上限。ZCode 的缓存命中按本轮有效输入计算。刷新失败时保留最近一次读到的数据，并标明它来自上次读取。

在独立悬浮窗中，暂停自动刷新之后仍可点「立即刷新一次」。再次点暂停按钮会恢复自动刷新。卡片模式可展开或收起速率曲线。

Codex 的整轮吞吐包含工具等待。ZCode 的生成速率按生成区段计算。缺少本轮数据时，相关主指标显示 `—`。已安装旧版独立 ZCode TPS 插件的用户可先在插件管理器停用它，避免重复状态项。

From this package directory:

~~~sh
node --test test/*.test.mjs
python3 -B -m unittest discover -s test -p '*_test.py'
node test/browser-smoke.mjs
node plugins/zcode/dashboard/overlay/smoke-test.mjs
python3 scripts/check-desktop-panel.py --codex /absolute/path/to/codex
~~~

The smoke tests use disposable fixtures and need access to a loopback port. The browser smoke requires Chrome. Set `CHROME_BIN` when its executable is outside PATH. It exercises browser rendering with simulated host bridges.

[Upstream and artwork notices](NOTICE.md)
