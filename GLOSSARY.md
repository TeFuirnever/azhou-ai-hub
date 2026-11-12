# Azhou AI Hub

Hub 编排仓库的领域词汇。此处只收项目特有概念，不收通用工程词汇。

## Language

**退役（decommission）**：
一个对象（包、宿主支持、能力）彻底移出维护面的范围决策，本仓口径＝物理删除。
_Avoid_：下线、冻结归档、弃用

**物理删除（physical deletion）**：
退役对象的源码与活引用移出仓库；来源可追溯性由 git 历史与 provenance 记录承担，不留死代码。
_Avoid_：保留源码标 unsupported

**退出声明（exit statement）**：
退役时随同一 commit 发布的公开陈述（双语 README + support-matrix）：最后支持版本、替代路径（如有）、已装用户处置。
_Avoid_：deprecation notice（本仓退役无过渡期，不是弃用）

**切割（cut）**：
新版本中退役面与存活面的边界：要求干净清楚——活引用零残留、无半死状态、冻结标识之外无 ZCode/Kit/旧包痕迹。
_Avoid_：渐进移除、软切割

**冻结标识（frozen identifier）**：
因已安装态迁移基线依赖而保留原名的持久化/协议标识（基线键、存储命名空间、owner id）；是"切割干净"的唯一豁免面。
_Avoid_：兼容别名（本仓不做改名+别名）

**回执属主交接（receipt ownership handoff）**：
Pet/App 回执属主从旧根迁往存续根的显式流程，交接回执经审阅是旧根物理删除的前置条件。
