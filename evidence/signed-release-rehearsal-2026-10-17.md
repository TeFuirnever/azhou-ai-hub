# Keyless 签名发布演练回据（T7，#225）

> 日期：2026-10-17（Asia/Shanghai）· 环境：GitHub Actions `ubuntu-latest` runner，Python 3.11，sigstore CLI `4.5.0`（pip 钉版）· 对象：`.github/workflows/signed-release-rehearsal.yml` 全流程（T7，parent #218）· 仓库状态：`main@276aa3c`
> 原始输出：Actions run `39017021484`（成功；step summary 与日志逐行留存），外加两次抓出缺陷的失败 run `39015183486`、`39016623432`。
> 隐私口径：全流程在 runner 临时目录内完成，无用户身份、无会话内容；签名身份为工作流自身的 OIDC 标识。

## 机制决定

签名机制采用 **keyless sigstore**（#225 的默认候选）：Fulcio 签发的短时证书 + Rekor 透明账本 bundle，无长期维护者密钥需要配置或保管。签名身份精确绑定到本仓库工作流——`https://github.com/TeFuirnever/azhou-ai-hub/.github/workflows/signed-release-rehearsal.yml@refs/heads/main`，OIDC issuer `https://token.actions.githubusercontent.com`。

## 执行与结果

| 步骤 | 命令/动作 | 结果 |
|---|---|---|
| 生成清单 | 遍历 `skills/` 下 14 个 canonical 包，逐文件 SHA-256 聚合为 `SKILL_SHA256SUMS.txt` | 成功 |
| Keyless 签名 | `python -m sigstore sign --bundle SKILL_SHA256SUMS.txt.sigstore SKILL_SHA256SUMS.txt`（GitHub Actions OIDC ambient 凭据） | 成功，产出 Rekor bundle |
| 身份验证 | `python -m sigstore verify identity --bundle … --cert-identity '<workflow uri>@refs/heads/main' --cert-oidc-issuer 'https://token.actions.githubusercontent.com' SKILL_SHA256SUMS.txt` | 成功：`OK: SKILL_SHA256SUMS.txt` |
| 草稿挂载 | draft release `signing-rehearsal-2026-10-17`（不发布、不公告），资产为清单 + `.sigstore` bundle | 成功 |

## 演练抓出的缺陷（本次演练的实质产出）

三次派发，前两次各暴露一个真实缺陷，均修复后才走通——这正是演练存在的意义：

1. **复合 action 无法通过本仓库 action 准入策略**（run `39015183486`，Set up job 阶段）：`sigstore/gh-action-sigstore-python` v3.5.0 内嵌 `softprops/action-gh-release`（带 `if: release` 守卫，但策略在 job setup 阶段无条件校验整个 composite 图）。#238 落地以来该工作流从未能真正运行。修复（#281）：改为 pip 钉版直装 CLI，`sigstore==4.5.0` 恰为 composite 自身 requirements 锁定的版本。
2. **sigstore 4.5.0 CLI 语法迁移**（codex 评审 P1，源码核实）：`verify-identity` → 嵌套子命令 `verify identity`，旗标改名 `--cert-identity` / `--cert-oidc-issuer`。
3. **`sign --bundle` 语义变化**（run `39016623432`）：4.x 的 `--bundle` 是显式输出路径，传输入文件自身会触发 `Refusing to overwrite outputs without --overwrite` 退出。修复（#282）：bundle 输出指向 `.sigstore` 路径。

## 边界与结论

- 签名对象是**发布资产清单**（per-skill 树摘要 + sigstore bundle），即"可下载产物出现时的签名形态"；Git tag 本身的签名未在本次演练范围内，待 tag 签名步骤引入并单独演练后才可声称。
- 按 `docs/releasing.md` 的口径，任何具体发布物在 GitHub 出示其可验证签名证据之前，不得声称已签名。
- #225 的三条验收标准全部满足：机制已决定并记录（本节）、一次带签名步骤的 draft 演练执行成功（run `39017021484`）、证据笔记已入库（本文件）；`docs/releasing.md` 的"直到真实演练"告警同步更新。
