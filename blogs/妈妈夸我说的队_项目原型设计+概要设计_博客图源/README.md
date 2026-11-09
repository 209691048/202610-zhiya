# 博客图源说明

本目录存放博客《2026秋软工实践 妈妈夸我说的队——项目原型设计+概要设计》使用的 18 张图片。发布时按同名文件上传，替换正文中的相对路径即可。

## 目录结构

```text
博客图源/
├── 01-原型/          # 后台原型截图、页面流转图
├── 02-架构与UML/     # 组件图、思维导图、活动图、类图、用例图、时序图
├── 03-数据库/        # 三张 ER 图
└── 04-部署/          # 部署图
```

## 文件对照

| 文件 | 博客图号 | 原始来源 |
|---|---|---|
| `01-原型/proto-flow.png` | 图1 | 本次为博客绘制（HTML + Chrome 渲染，2 倍缩放） |
| `01-原型/proto-workbench.png` | 图2 | `prototype/admin-html` 实机截图（1440×960，2x） |
| `01-原型/proto-review.png` | 图3 | 同上 |
| `01-原型/proto-knowledge.png` | 图4 | 同上 |
| `02-架构与UML/sys-components.png` | 图5 | 系统设计说明书 图 4-1（`docs/design/diagrams/system/fig-4-01-system-components.png`） |
| `02-架构与UML/sys-mindmap.png` | 图6 | 需求规格说明书 2.6 节（`docs/requirements/images/mindmap.png`） |
| `02-架构与UML/sys-dataflow.png` | 图7 | 系统设计说明书 图 4-2 |
| `02-架构与UML/sys-activity-reading.png` | 图8 | 系统设计说明书 图 5-3 |
| `02-架构与UML/sys-state-session.png` | 图9 | 系统设计说明书 图 6-1 |
| `02-架构与UML/sys-use-case-reader.png` | 图10 | 系统设计说明书 图 3-1 |
| `02-架构与UML/sys-class-domain.png` | 图11 | 系统设计说明书 图 5-1 |
| `02-架构与UML/sys-seq-agent.png` | 图12 | 系统设计说明书 图 5-5 |
| `02-架构与UML/sys-seq-voice.png` | 图13 | 系统设计说明书 图 5-7 |
| `02-架构与UML/sys-collab-guidance.png` | 图14 | 系统设计说明书 图 5-8 |
| `04-部署/sys-deployment.png` | 图15 | 系统设计说明书 图 8-1 |
| `03-数据库/db-er-auth.png` | 图16 | 数据库设计说明书 图 4-1 |
| `03-数据库/db-er-story.png` | 图17 | 数据库设计说明书 图 4-2 |
| `03-数据库/db-er-knowledge.png` | 图18 | 数据库设计说明书 图 4-3 |

说明：

- 博客只放主干图，其余图（分支选择、续写切换、请求占位、生成校验、内容管理用例、服务类图等）保留在仓库 `docs/design/diagrams/`，按图号命名，可直接对应。
- 系统说明书与数据库说明书共用一张数据关系图（系统图 7-1 / 数据库图 4-2），博客只在第三章引用一次，即 `db-er-story.png`。
- 后台截图为真实运行画面，未做界面重绘；如需更新，打开 `prototype/admin-html` 后重新截图。

## 更新记录

| 日期 | 变更 |
|---|---|
| 2026-11-09 | 与定稿博客对齐：正文共引用 18 张图（图1～图18），目录与之一一对应；其中 14 张取自仓库 `docs/design/` 与 `docs/requirements/` 原图，4 张为本次生成（页面流转图 1 张 + 后台实机截图 3 张）。此前版本中未被正文引用的 8 张图已移出本目录。 |

核对方式：正文 `![图n ...](博客图源/...)` 的引用与上表逐行比对；14 张仓库原图用 SHA-256 与 `docs/design/diagrams/`、`docs/requirements/images/` 下同名文件比对一致，4 张自生成图（图1 与三张后台截图）按尺寸与内容核对。
