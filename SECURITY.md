# 安全政策

## 报告漏洞

如果你发现了安全漏洞，请**不要**通过公开 Issue 提交。

请通过以下方式私密报告：

1. 在 GitHub 仓库（x2it/zhixing-workbench）创建 **Security Advisory**（建议优先）
2. 或直接联系知行工作室维护者

请在报告中包含：
- 漏洞的详细描述（影响面、风险等级评估）
- 可复现的步骤 / PoC
- 建议的修复方案（如有）

## 响应时间

- 确认收到：**48 小时内**
- 初步评估：**7 天内**
- 修复发布：视严重程度而定；高危漏洞单独发布修补版本

---

## 数据安全说明（与代码一致）

### 1. 密码存储

知行工作台**不保存密码明文**。保存的是：

- **PBKDF2-HMAC-SHA256** 派生哈希（100,000 次迭代，随机 salt 由 hashlib 内部处理）
- 判定首次运行 `is_first_run()`：仅当 `password_hash` 等于初始化占位哈希 AND 无 enc_data 时 → 进入 SetupPasswordFrame 引导用户自建密码
- 修改密码时必须提供当前密码才能生成新的 password_hash

> 重要：首次运行 **没有默认密码**，走 SetupPasswordFrame 引导用户自行创建（≥ 6 位），不会硬编码任何值。

### 2. 敏感数据加密（todos / notes / shortcuts）

- 登录成功 → `config.unlock(password)`：用 PBKDF2 从密码派生 AES 密钥 → 解密 `enc_data`（流式加密 JSON）
- 保存时 → `config.save()`：敏感数据 AES 加密后写入 `enc_data`；**密码只保留在内存 `_password` 字段，永不落盘**
- 未登录临时态：todos / notes / shortcuts 以明文单独文件保存（`todos.json` / `notes.json` / `shortcuts.json`），保证关机不丢；**下次登录成功后会自动合并进 enc_data 并清空明文**

### 3. 所有数据本地存储，零网络

知行工作台**不发起任何网络请求**（除了快捷启动「网址」类项目由你点击主动打开浏览器）。

- 安装版：`~/.zhixing_workbench/`
- 便携版：程序同级 `data/`
- 自动迁移合并仅发生在本地两个目录之间，不联网

### 4. 自动锁屏

v2.3.18 起支持自动锁屏：
- 全局监听鼠标 / 键盘交互（仅在应用内事件，不使用全局键盘钩子）
- 每 30s tick，阈值到 → 显示 🔒 LockScreenFrame；若开了窗口停靠则同步 `withdraw()` 到托盘
- 锁屏界面用独立密码框校验，错误时 shake + 提示，不连续锁定也不做次数熔断（风险本地可控）

### 5. AppUserModelID

v3.0 起进程级 + 窗口级 + 快捷方式三层写入 `ZhixingStudio.Workbench.v3`：
- 防止恶意程序通过窗口 AppID 冒用本应用的任务栏固定项与跳转列表
- 确保右键「固定到任务栏」后图标 / 名字正确关联本应用

---

## 杀毒软件误报说明

由于本应用使用 **PyInstaller**（onedir 模式）打包，部分国产杀毒软件（360、火绒、Windows Defender 等）可能出现误报。

这是 PyInstaller 打包程序的普遍现象：
- PyInstaller 将 Python 解释器 + 字节码打包在一个 EXE / PYZ 中，其 PE 结构与"加壳工具"类似，启发式引擎可能误判
- 应用本身不含任何恶意代码（无网络请求、无注入、无文件系统越权）
- 你可直接从 `main.py` + `requirements.txt` 源码自行 `pyinstaller ZhixingWorkbench.spec` 构建

如遇误报：
1. 在对应杀毒软件中将 `知行工作台.exe` 或程序目录添加信任
2. 扫描文件上传至 VirusTotal 综合核对（应为 0/70 或少量误报）
