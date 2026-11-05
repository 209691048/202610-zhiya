# 知芽 v1.1 图源与图片

整理日期：2026-11-05。图号对应已复核的系统设计说明书 v1.1 与数据库设计说明书 v1.1。


## 来源与本次提交

- 原始图源及配套 PNG、SVG 由林鑫提供，来自 2026-11-05 群内的 `zhiya-design-diagrams-v1.1.zip`。
- 姚华俊（082403146）按团队约定补交到 `docs/design/diagrams/`，补充图号索引与预览入口，并检查文件完整性和配套关系。图的设计内容及生成脚本均保留原包内容。
- 对应已合并的[系统设计说明书](../妈妈夸我说的队_系统设计说明书.pdf)和[数据库设计说明书](../妈妈夸我说的队_数据库设计说明书.pdf)，交付背景见 [PR #3](https://github.com/coderbrain404/202610-zhiya/pull/3)。
- 目录按说明书区分为 `system/`、`database/`，保留每张图的 `.puml`、`.png`、`.svg` 三种格式；共用 ER 图需要同步维护。

## 命名与内容

按项目规范使用 `fig-章节号-两位序号-英文主题`，如 `fig-5-06-branch-sequence.puml`，英文主题采用 kebab-case。同一张图的 `.puml`、`.png`、`.svg` 使用相同文件名主体。

- `system/`：系统说明书的 18 张图。
- `database/`：数据库说明书的 4 张图。
- 每张图提供 PlantUML 源码、PNG 图片、SVG 矢量图。
- 包含 UML 及说明书配套的 ER 图、数据流图，图类型以正文和图题为准。

两份文档共用一张 ER 图：`system/fig-7-01-data-relations` 对应 `database/fig-4-02-data-relations`。因此按文档图号提供 22 组文件，实际为 21 张不同的图。共用图的三种格式内容完全一致；修改后应同步两处。

本次只整理文件名和目录，保留已复核的图文与连线，不修改图的设计内容。

## 图号对照

| 所属文档 | 图题 | 源码文件 | 图片预览 |
| --- | --- | --- | --- |
| 系统 | 图3-1 阅读用户用例图 | [fig-3-01-reader-use-cases](system/fig-3-01-reader-use-cases.puml) | [PNG](system/fig-3-01-reader-use-cases.png) · [SVG](system/fig-3-01-reader-use-cases.svg) |
| 系统 | 图3-2 原创故事与内容管理用例图 | [fig-3-02-content-use-cases](system/fig-3-02-content-use-cases.puml) | [PNG](system/fig-3-02-content-use-cases.png) · [SVG](system/fig-3-02-content-use-cases.svg) |
| 系统 | 图4-1 系统组件与依赖图 | [fig-4-01-system-components](system/fig-4-01-system-components.puml) | [PNG](system/fig-4-01-system-components.png) · [SVG](system/fig-4-01-system-components.svg) |
| 系统 | 图4-2 阅读业务数据流图 | [fig-4-02-data-flow](system/fig-4-02-data-flow.puml) | [PNG](system/fig-4-02-data-flow.png) · [SVG](system/fig-4-02-data-flow.svg) |
| 系统 | 图5-1 核心领域类图 | [fig-5-01-domain-classes](system/fig-5-01-domain-classes.puml) | [PNG](system/fig-5-01-domain-classes.png) · [SVG](system/fig-5-01-domain-classes.svg) |
| 系统 | 图5-2 核心服务类图 | [fig-5-02-service-classes](system/fig-5-02-service-classes.puml) | [PNG](system/fig-5-02-service-classes.png) · [SVG](system/fig-5-02-service-classes.svg) |
| 系统 | 图5-3 阅读主流程活动图 | [fig-5-03-reading-activity](system/fig-5-03-reading-activity.puml) | [PNG](system/fig-5-03-reading-activity.png) · [SVG](system/fig-5-03-reading-activity.svg) |
| 系统 | 图5-4 原创故事生成与审核活动图 | [fig-5-04-original-activity](system/fig-5-04-original-activity.puml) | [PNG](system/fig-5-04-original-activity.png) · [SVG](system/fig-5-04-original-activity.svg) |
| 系统 | 图5-5 阅读智能体任务时序图 | [fig-5-05-agent-sequence](system/fig-5-05-agent-sequence.puml) | [PNG](system/fig-5-05-agent-sequence.png) · [SVG](system/fig-5-05-agent-sequence.svg) |
| 系统 | 图5-6 分支选择与幂等提交时序图 | [fig-5-06-branch-sequence](system/fig-5-06-branch-sequence.puml) | [PNG](system/fig-5-06-branch-sequence.png) · [SVG](system/fig-5-06-branch-sequence.svg) |
| 系统 | 图5-7 语音问答与文字回退时序图 | [fig-5-07-voice-sequence](system/fig-5-07-voice-sequence.puml) | [PNG](system/fig-5-07-voice-sequence.png) · [SVG](system/fig-5-07-voice-sequence.svg) |
| 系统 | 图5-8 动态引导协作图 | [fig-5-08-communication](system/fig-5-08-communication.puml) | [PNG](system/fig-5-08-communication.png) · [SVG](system/fig-5-08-communication.svg) |
| 系统 | 图5-9 智能体内部生成与校验时序图 | [fig-5-09-agent-validation-sequence](system/fig-5-09-agent-validation-sequence.puml) | [PNG](system/fig-5-09-agent-validation-sequence.png) · [SVG](system/fig-5-09-agent-validation-sequence.svg) |
| 系统 | 图5-10 模型调用前请求占位时序图 | [fig-5-10-request-idempotency-sequence](system/fig-5-10-request-idempotency-sequence.puml) | [PNG](system/fig-5-10-request-idempotency-sequence.png) · [SVG](system/fig-5-10-request-idempotency-sequence.svg) |
| 系统 | 图5-11 续写版本审核与会话原子切换时序图 | [fig-5-11-continuation-sequence](system/fig-5-11-continuation-sequence.puml) | [PNG](system/fig-5-11-continuation-sequence.png) · [SVG](system/fig-5-11-continuation-sequence.svg) |
| 系统 | 图6-1 阅读会话状态图 | [fig-6-01-session-state](system/fig-6-01-session-state.puml) | [PNG](system/fig-6-01-session-state.png) · [SVG](system/fig-6-01-session-state.svg) |
| 系统 | 图7-1 核心业务数据关系图 | [fig-7-01-data-relations](system/fig-7-01-data-relations.puml) | [PNG](system/fig-7-01-data-relations.png) · [SVG](system/fig-7-01-data-relations.svg) |
| 系统 | 图8-1 软件独立部署图 | [fig-8-01-deployment](system/fig-8-01-deployment.puml) | [PNG](system/fig-8-01-deployment.png) · [SVG](system/fig-8-01-deployment.svg) |
| 数据库 | 图4-1 账号、儿童授权与请求执行关系 | [fig-4-01-auth-reading-er](database/fig-4-01-auth-reading-er.puml) | [PNG](database/fig-4-01-auth-reading-er.png) · [SVG](database/fig-4-01-auth-reading-er.svg) |
| 数据库 | 图4-2 绘本本体、版本与阅读记录 | [fig-4-02-data-relations](database/fig-4-02-data-relations.puml) | [PNG](database/fig-4-02-data-relations.png) · [SVG](database/fig-4-02-data-relations.svg) |
| 数据库 | 图4-3 事件与实际引用的知识版本 | [fig-4-03-knowledge-er](database/fig-4-03-knowledge-er.puml) | [PNG](database/fig-4-03-knowledge-er.png) · [SVG](database/fig-4-03-knowledge-er.svg) |
| 数据库 | 图5-1 阅读、模型调用及结果保存时序 | [fig-5-01-reading-sequence](database/fig-5-01-reading-sequence.puml) | [PNG](database/fig-5-01-reading-sequence.png) · [SVG](database/fig-5-01-reading-sequence.svg) |

## 编辑与重新生成

修改 `.puml` 后，用 Java 和 PlantUML 生成同名 PNG、SVG。既有渲染环境为 PlantUML 1.2026.9、Graphviz 16.1.0 和 Microsoft YaHei 字体。

```text
java -jar <plantuml.jar绝对路径> -charset UTF-8 -tpng <图源文件.puml>
java -jar <plantuml.jar绝对路径> -charset UTF-8 -tsvg <图源文件.puml>
```

系统的数据流图 `fig-4-02-data-flow` 和部署图 `fig-8-01-deployment` 需要继续运行 `system/route-deployment-and-data-flow.py`，保留分离的连线端口。该脚本使用 Python、Java、Graphviz、Node.js 与 sharp；请为本机配置 `PLANTUML_JAR`、`GRAPHVIZ_DOT`、`ZHIYA_JAVA`、`ZHIYA_NODE`、`ZHIYA_SHARP` 的绝对路径。脚本沿用 Windows 字体路径及原环境默认值，不能直接假定其他机器已安装相同工具；配置上述变量后再运行。改变节点或画布时须同步检查脚本坐标。

更新后核对图号、文字、箭头、线条与正文引用，再替换说明书中的图片。
