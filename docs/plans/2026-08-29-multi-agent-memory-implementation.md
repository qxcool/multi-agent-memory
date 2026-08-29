# Multi-Agent Memory 实施计划

**目标：** 重建可公开安装、兼容旧数据并支持多代理安全并发的共享记忆插件。

**架构：** 宿主无关 Skill 负责工作流选择，Python 标准库实现确定性 CLI，Markdown 文件作为可审阅的唯一事实来源。仓库提供通用 Skill、可选 Codex 市场清单与独立 Python 包。

**技术栈：** Python 3.10+、`unittest`、Agent Skill、可选 Codex Plugin、GitHub Actions。

## 任务一：兼容存储内核

- 建立 `MemoryHub`、原子写入和跨平台锁。
- 实现初始化、状态、候选记忆、检索、上下文、归档、索引和健康检查。
- 验证非法任务名不能越出记忆库。

## 任务二：命令行与旧接口

- 保留全局 `--hub` 和旧子命令参数。
- 增加 `--json`、`context`、`doctor`。
- 用子进程测试真实入口脚本和 JSON 输出。

## 任务三：插件封装

- 编写 `.codex-plugin/plugin.json` 与仓库级市场清单。
- 编写 Skill 入口、按需命令参考和存储格式参考。
- 校验插件清单、Skill 前置元数据和相对路径。

## 任务四：公开发布

- 补齐 README、架构、安全、贡献和许可证文件。
- 在三个操作系统和多个 Python 版本上运行 CI。
- 对真实旧库进行只读兼容验证，创建公开 GitHub 仓库并推送首个版本。
