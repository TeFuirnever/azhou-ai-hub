# Azhou Agent Inspector · 阿舟 Agent 透视台

Azhou AI Hub 的 Agent 状态透视模块。当前版本提供 Performance，展示各宿主的原生会话性能。两个宿主的插件 ID 均为 `azhou-agent-inspector`，运行时由各自的插件管理器负责。市场目录使用本包的绝对路径。

| 宿主 | 安装 | 使用 |
|---|---|---|
| Codex Desktop | `codex plugin marketplace add /absolute/path/to/azhou-ai-hub/packages/azhou-agent-inspector`，再运行 `codex plugin add azhou-agent-inspector@azhou-agent-tools` | 打开会话侧面板，选择阿舟 Agent 透视台，刷新本轮数据。需要 Python 3 和本地 rollout 记录。 |
| ZCode Desktop 3.18.2+ | 在 ZCode 运行 `/plugin marketplace add /absolute/path/to/azhou-ai-hub/packages/azhou-agent-inspector`，再运行 `/plugin install azhou-agent-inspector@azhou-agent-tools` | 输入框底部显示生成速率，点击打开会话仪表盘。辅助命令包括 `/tps`。需要 Node.js。 |

Codex 的整轮吞吐包含工具等待。ZCode 的净生成速率按生成区段计算。缺少计量时 Codex 面板显示缺失状态。已安装旧 ZCode 插件的用户可先在插件管理器停用旧插件，避免重复状态项。

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
