# 贡献指南

欢迎提交问题、文档修正和小而明确的改进。涉及存储格式或旧命令行为的变更，请先说明兼容影响。

提交前请运行：

```powershell
python -m unittest discover -s plugins/multi-agent-memory/tests -v
```

新增行为应包含可观察结果的测试。测试不得访问网络、真实用户目录或修改现有 `.ai-memory-hub`。提交信息建议使用 `feat:`、`fix:`、`docs:`、`test:` 等清晰前缀。
