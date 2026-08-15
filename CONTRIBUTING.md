# 贡献指南

欢迎提交 Issue 和 PR。

## 如何贡献

1. Fork 本仓库
2. 创建分支：`git checkout -b feature/your-feature`
3. 提交更改：`git commit -m "Add your feature"`
4. 推送：`git push origin feature/your-feature`
5. 发起 Pull Request

## 规范

- Python 代码保持**纯标准库**实现，不引入第三方依赖
- 确保 `flake8 . --select=E9,F63,F7,F82` 无报错
- 新功能请同步更新对应 `SKILL.md`
- 提交信息用英文，简洁描述改动

## 许可证

提交的代码将遵循 [GPL-3.0](LICENSE) 许可证。
