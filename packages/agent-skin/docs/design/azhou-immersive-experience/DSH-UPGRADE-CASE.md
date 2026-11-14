# 用 DSH rc.1 到 rc.3 验证防腐层

## 已知版本与未验证状态

本案例落实用户要求，用真实DSH升级验证防腐层，而不只靠模拟fixture。

2026-11-14只读检查确认已安装包的CFBundleShortVersionString与CFBundleVersion均为 `0.2.2-rc.1`，bundle为 `com.deepseek.dsh`。安装元数据不证明正在运行实例及插件的实际加载版本。

官方应用配置使用nightly通道。[官方mac-arm64 feed](https://download.deepseek.com/dsh-desk/feeds/mac-arm64/nightly-mac.yml)本次返回 `0.2.2-rc.3`，releaseDate为 `2026-11-13T07:40:14.455Z`，大小362840431字节并提供SHA-512。[官方rc.3发布记录](https://github.com/deepseek-ai/deepseek-harness/releases/tag/dsh-v0.2.2-rc.3)为prerelease，发布于同日07:56:55Z，不能称稳定版。执行时重新读取并冻结准确地址、摘要、签名和候选，不静默追逐变化中的nightly。

相关源码 `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159` 对应rc.1。另一旧checkout为0.2.1-alpha.1，不是当前安装基线。源码revision不能代替应用摘要。rc.3尚未下载、安装或运行。

## 共享实体不等于隔离

当前桌面、验证和web三个profile的Agent Skin链接指向同一0.9.0实体。验证profile名称不证明载荷隔离。先冻结完整实体摘要、链接解析与所有权，不修改共享实体。新旧宿主需真正独立候选和明确profile数据边界，不复制账号、聊天或未知数据库。

适配依赖包括ModuleLoader.load、own DSH boot标记、唯一main slot、主题属性、dsw颜色token、pageBar、composerSeat与page类名模式。settings.section、slots及ctx.effect清理也是契约，不只测试壁纸出现。

## 执行步骤

1. 记录实际运行bundle、profile、插件实体、来源、签名、version、build与摘要，分别报告installed和loaded。
2. 保留rc.1应用及插件恢复依据，确认全部共用profile和安装owner。不得关闭用户活跃会话来取得测试结果。
3. 冻结rc.1能力报告与现有缺陷。核对早期hook、CSP、设置入口、生命周期及真实工作区。基线缺陷不算升级回归。
4. 复核官方feed与目标。下载后校验SHA-512、签名、arm64架构和实际build。下载成功不等于可运行或兼容。
5. 选择官方支持的独立测试安装或profile方式。没有安全隔离方法则保持blocked，不覆盖共享实体。实际安装、启动及数据操作另走授权和本地安装SOP。
6. 同一冻结Agent Skin候选分别探测rc.1与rc.3。证据绑定version、build、adapter revision、schema和page generation。旧ready失效。必要修正只在Hub宿主适配器，不修改DSH官方源码，不让核心猜选择器。
7. 两版分别执行 [防腐层故障矩阵](HOST-BOUNDARY.md)、冷启、设置、整窗外观、路由、跳过及原生输入发送。静态fixture不能代替真实版本验收。
8. 演练缺hook、CSP拒绝、未知schema及另一主题冲突。只停受影响皮肤能力，解除自有遮挡，保留原生操作和用户数据。
9. 演练回退并核对实际加载身份。先确认profile迁移可逆性，应用回退不代表数据库可逆。禁止把新数据库交给旧版冒险打开。
10. 更新支持矩阵。只有rc.3真实验收后增加相应支持；只有静态证据则记live pending，不称升级完成。

## 任务与完成条件

P01冻结目标和权属，P10实现版本绑定与失败安全，P05只接入已证明支持的DSH入口，P06分端收尾。P05直接依赖P10。P10在P02协议冻结后完成共享契约、Codex子集及DSH故障fixture。DSH真实rc.1到rc.3 lane由P05完成，未通过不得宣称全端完成。

证据至少包括两版精确身份、相同插件候选、结构差异、能力报告、真实录屏、失配降级及回退。无法隔离、候选不可获取、迁移不可逆或需要结束用户会话均为具体阻塞，不凭推断补齐。

本次只保存设计与只读版本调查。未下载、安装、重启DSH，未修改源码、profile或共享插件实体。
