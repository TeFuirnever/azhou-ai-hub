# Research: OpenSSF Best Practices 徽章注册前草拟自评（#27）

> 日期：2026-09-13（Asia/Shanghai）
> 性质：注册前准备文档。注册动作本身需要 maintainer 账号在 www.bestpractices.dev 交互完成，本文不关闭 #27 的对应 checkbox，也不改变任何公开声明。
> 依据：Passing（tier 0）与 Silver（tier 1）官方 criteria（www.bestpractices.dev/en/criteria/0 与 /1，2026-09-13 抓取）；OpenSSF Scorecard API 快照 `2026-09-13T01:54:35Z`（score 6.9，commit `2efa3b9`）。

## 结论

- **Passing 档当前即可全部作答**：唯一成组 N/A 的是密码学条款（本仓库与其分发物不实现、不调用、不强依赖任何密码学组件）。
- **Silver 档有真实差距**：`bus_factor`、`access_continuity`、`dco`、`governance`、`roles_responsibilities`、`code_of_conduct`、`documentation_roadmap`、`signed_releases` 等——与 #27 其余 checkbox 同源（第二维护者、签名发布），不为了分数硬凑。
- **Scorecard 与 #27 清单的差异**（快照见下文）：`Fuzzing` 检查项为 0——PR #91 的 fuzzer 是仓库自带的标准库确定性变异 fuzzer，Scorecard 只识别 OSS-Fuzz/语言原生等已知模式，这一分不是"没做"而是"启发式不识别"；`CII-Best-Practices` 为 0——即本文针对的注册项。

## 注册 runbook（maintainer，约 15–30 分钟）

1. 打开 https://www.bestpractices.dev ，用 GitHub 账号（TeFuirnever）登录。
2. "Add Your Project" → 填入 repo URL `https://github.com/TeFuirnever/azhou-ai-hub`，创建条目。
3. 按 §Passing 档答案表逐条填写；每条都已给出建议答案与仓库内证据位置。
4. 提交后条目进入 in-progress；全程保存即可悬挂徽章状态。
5. 通过后 **48 小时内**把徽章加入 README（对应 criterion `documentation_achievements`）。注意：README 在 super-caveman promotion receipt 的 reviewed 集内，按 `AGENTS.md` 的 Verification 段走 promotion 流程落地。

## Passing 档答案表

图例：✅=满足，N/A=不适用（表单中选 "N/A" 并给出理由）。

### Basics

| Criterion | 答案 | 证据 |
|---|---|---|
| description_good / interact | ✅ | `README.md` 首段说明软件做什么、解决什么问题；安装（`npx skills add ...`）、反馈与贡献路径齐备 |
| contribution / contribution_requirements | ✅ | `CONTRIBUTING.md`：以真实任务与可复现证据为起点，声明 `docs/skill-standard.md` 为包级权威；明确中文 issue/PR 可接受、机器字段保持英文 |
| floss_license / floss_license_osi / license_location | ✅ | `LICENSE`（MIT，OSI 批准），仓库标准位置；第三方携带许可见根目录各 `*-MIT.txt`/`*-Apache-2.0.txt` |
| documentation_basics | ✅ | 双语 README、`docs/skill-standard.md`、`docs/support-matrix.md`、`docs/installation.md` 等 |
| documentation_interface | ✅ | 每个 canonical skill 的 `SKILL.md` 入口合同与 references（如 `skills/session-insights/references/report-contract.md` 的 CLI 口径）；声明"便携运行不意味着 hooks/内存 API 等同" |
| sites_https | ✅ | 仓库、分发、issue 全部经由 GitHub HTTPS |
| discussion | ✅ | GitHub Issues：可检索、URL 可寻址、对新来者开放、无私有客户端要求 |
| english | ✅ | README 英文为公共入口，英文 issue/PR 明确可接受 |
| maintained | ✅ | 近 90 天持续合并与发布（v0.4.1→v0.9.0 及其后连续落地）。注意 Scorecard `Maintained=0` 是"仓库创建不足 90 天"的保守信号，作答时以实际活动为准 |

### Change Control

| Criterion | 答案 | 证据 |
|---|---|---|
| repo_public / repo_track / repo_interim / repo_distributed | ✅ | 公开 GitHub 仓库；git 记录 what/who/when；PR 粒度即中间版本；git DVCS |
| version_unique / version_semver / version_tags | ✅ | `v0.4.1`…`v0.9.0` 唯一递增 tag；Keep a Changelog + 仓库级 SemVer |
| release_notes | ✅ | `CHANGELOG.md` 每条为人工撰写的变更摘要，非裸 VCS log |
| release_notes_vulns | ✅（none so far） | 至今无已修复的公开已知漏洞可列；表单答 "no publicly known vulnerabilities fixed yet"，不虚构 CVE |

### Reporting

| Criterion | 答案 | 证据 |
|---|---|---|
| report_process / report_tracker / report_archive | ✅ | GitHub Issues 即流程、追踪器与公开可检索档案 |
| report_responses / enhancement_responses | ✅ | 以近 2–12 个月真实响应记录作答；当前量级下全部有响应 |
| vulnerability_report_process / vulnerability_report_private | ✅ | `SECURITY.md`：私有披露通道（GitHub private vulnerability reporting），禁止公开 issue 报安全洞 |
| vulnerability_report_response | ✅ | `SECURITY.md` §Response targets：公开披露前 14 天内初始响应、修复期间至少每 14 天一次状态更新 |

### Quality

| Criterion | 答案 | 证据 |
|---|---|---|
| build / build_common_tools / build_floss_tools | ✅ | 纯 Python 3.11+ 标准库，无构建产物；`python3 scripts/verify.py` 即可从源码完整复验 |
| test / test_invocation / test_most / test_continuous_integration | ✅ | `scripts/verify.py`（仓库策略 + 466 项单测 + 全部注册 benchmark 完整性套件）；GitHub Actions 在 Linux 与 Windows 双平台强制执行 |
| test_policy / tests_are_added / tests_documented_added | ✅ | `docs/skill-standard.md` 的确定性门与负控要求；近期每个 feature PR 均附验收勾选与配套测试（如 #209/#210/#211/#212 的 golden 与负控） |
| warnings / warnings_fixed / warnings_strict | ✅（按语言等价作答） | Python 无编译告警面；等价严格面是仓库门禁（`scripts/check_repository.py` 策略检查、whitespace 检查、fidelity/rename-residue 负控），违反即红 |

### Security

| Criterion | 答案 | 证据 |
|---|---|---|
| know_secure_design / know_common_errors | ✅（maintainer 自证） | 安全设计与常见漏洞知识体现在实践里：只读观察者边界、fail-closed 合同、最小权限 CI（全 SHA pin、只读默认 token、无 `pull_request_target` 不可信 checkout） |
| crypto_*（整组） | N/A | 本仓库与其分发物不实现、不调用、不强依赖密码学组件；表单逐条选 "N/A" 并给此理由 |
| delivery_mitm / delivery_unsigned | ✅ | 分发仅经 GitHub HTTPS；无经明文 http 取哈希的场景 |
| vulnerabilities_fixed_60_days / vulnerabilities_critical_fixed | ✅ | 无已知未修复漏洞；Dependabot + CodeQL + dependency review 持续在跑 |
| no_leaked_credentials | ✅ | secret scanning 与 push protection 开启；fixture 中的密钥形状串均为运行时合成、不入库 |

### Analysis

| Criterion | 答案 | 证据 |
|---|---|---|
| static_analysis / static_analysis_often / static_analysis_common_vulnerabilities | ✅ | CodeQL（python + javascript-typescript）随每次 push/PR 运行（`.github/workflows/codeql.yml`），即常见漏洞导向且每次提交都跑 |
| static_analysis_fixed | ✅ | 发现项按 SECURITY/CONTRIBUTING 流程修复；当前无未处理确认项 |
| dynamic_analysis / dynamic_analysis_fixed / dynamic_analysis_enable_assertions | ✅（如实描述） | `scripts/fuzz_relay_state.py`：标准库确定性种子变异 fuzzer，CI `.github/workflows/fuzz.yml` 每次提交短跑 + 周度深跑；曾发现并修复 5 类真实崩溃（均有回归测试），修复后约 45 万输入保持清洁。如实写明这是自定义 stdlib fuzzer（Scorecard 启发式因此不给 Fuzzing 分，但徽章自评以证据为准） |

## Silver 差距清单（不做Fake）

| Criterion | 差距 | 归属 |
|---|---|---|
| bus_factor / access_continuity / roles_responsibilities / governance / dco | 单维护者 | #27 "require one approving review after a second trusted maintainer" 同源；有第二维护者后一并补治理文档 |
| code_of_conduct | 未发布 CoC | 低成本可补：采纳 Contributor Covenant 放 `.github/CODE_OF_CONDUCT.md`（maintainer 认可后落地） |
| documentation_roadmap | 无正式 roadmap 文档 | 可从 #161/#27 等现存计划提炼（maintainer 审定目标即可写） |
| signed_releases / version_tags_signed | release 无签名产物 | 需要签名密钥管理与维护者决策；当前为纯源码分发，可先在表单如实说明 |
| test_statement_coverage80 / regression_tests_added50 | 无覆盖率度量 | 可后续引入 coverage 统计再作答，不预先承诺 |

## 边界

本文只是注册前的准备与证据映射：不修改 #27 的 checkbox，不新增任何公开支持声明；enrollment 是 maintainer 的交互动作。若徽章通过，README 加徽章属 receipt pin 集编辑，按 `AGENTS.md` 走 promotion 流程。
