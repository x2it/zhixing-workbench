# 知行工作台

> 知行工作室 出品 · 个人桌面工作台应用 v3.0

一款集成快捷启动、待办管理、番茄钟计时、密码保险箱等功能的 Windows 桌面效率工具。
基于 Python + CustomTkinter 开发，界面采用扁平化简约设计风格。

## 功能特性

- **快捷启动**：分类管理常用应用 / 系统工具 / 网页书签，支持图标自动提取
- **待办管理**：任务增删改查、完成状态切换、番茄钟计时联动
- **番茄钟**：专注 / 休息循环计时，锁屏后基于绝对时间戳自动恢复，支持暂停 / 继续 / 重置
- **密码保险箱**：AES 加密存储敏感信息，主密码保护
- **数据看板**：使用统计与可视化
- **主题切换**：浅色 / 深色 / 跟随系统

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.10+ |
| UI 框架 | CustomTkinter 5.2+ |
| 图像处理 | Pillow (PIL) |
| 打包 | PyInstaller (onedir) |
| 安装包 | NSIS 3 |
| 系统集成 | ctypes (AppUserModelID / Shell API) |

## 快速开始

### 从源码运行

```bash
pip install -r requirements.txt
python main.py
```

### 打包构建

```bash
# 便捷版 (onedir)
pyinstaller --clean --noconfirm ZhixingWorkbench.spec

# 安装版 (需 NSIS 3)
makensis setup_installer.nsi
```

## 版本

当前版本：**3.0.0**

## 许可证

[MIT License](LICENSE) - Copyright (c) 2026 知行工作室

## 相关

- [更新日志](CHANGELOG.md)
- [贡献指南](CONTRIBUTING.md)
- [安全政策](SECURITY.md)
- [帮助手册](帮助手册.md)
