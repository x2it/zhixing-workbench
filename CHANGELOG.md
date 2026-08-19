# 更新日志

所有 notable 变更记录在此文件中。格式基于 [Keep a Changelog](https://keepachangelog.com/)，
版本号基于 [Semantic Versioning](https://semver.org/lang/zh-CN/)。

---

## [Unreleased] - 待发布（当前迭代 · 不升版号）

### 变更
- **番茄钟状态显示 优雅+有质感+扁平化 重排（v7）**：
  - 把 1 个粗糙单 Label 拆为 3 控件分层次：倒计时（Consolas 20 bold，大粗等宽数字）/ 状态中文（微软雅黑 15 normal），字体和字号的层级差异形成质感
  - 去掉生硬的竖线 `│` → 中性灰小圆点「·」做软分隔
  - 状态尾部去重复 emoji（🍅/☕ 统一交给外层卡片按钮和面板颜色承载）
  - 面板背景调淡 1 号（gray86/gray18）+ 1px 细边（gray80/gray24），从"突兀深色块"变成"卡片内嵌区域"

### 修复
- **番茄钟状态文案不通顺（「暂停·工作」动宾歧义）**：
  - 改为番茄法心智词「专注」，4 态统一：`专注中 / 休息中 / 暂停专注 / 暂停休息`（主谓结构，秒懂"当前暂停的是专注阶段"）
  - 进一步彻底纯平：去掉小圆点「·」，时间数字右侧直接 `padx=20` 纯留白做视觉分隔，100% 无字元干扰
- **完整发布包 ZIP 中「01_源码」目录缺失**：打包脚本在 SRC 根目录所有子目录都被 exclude 过滤时，从未创建 `01_源码` 目标目录自身，导致 copy2 全部 FileNotFound 被静默吞 → 强制先 `mkdir(src_dir)`，并新增复制成功/跳过/错误统计打印

---

## [3.2.0] - 2026-08-18

### 新增
- **快捷启动拖拽导入（文件→卡片）**：支持将 Windows 任意文件 / 快捷方式（.exe · .lnk · .url · .website · .doc · .docx · .xls · .xlsx · .ppt · .pptx · .pdf · .txt · .msc · .cpl · .bat · .cmd 等）直接拖到快捷启动卡片区域，自动按扩展名推断「软件 / 网址 / 系统命令 / 办公文档 / 管理工具」分类并填入路径、名称、图标
  - 解析引擎：tkinterdnd2（TkDND tkdnd.dll）+ 递归注册 scroll/grid_frame 子控件为 DnD 接收端；对 {path1}{path2} 多文件包裹格式做清理
  - 失败兜底：未识别的扩展名默认落在「软件」分类，保留原始路径让用户手动调整
- **一键刷新全部图标**：快捷启动右上角新增「🔄 刷新图标」按钮（110×34 灰色圆角），点击二次确认后按项目类型重新提取图标（软件→ exe 资源、系统命令→ Shell32 识别、网址→ 抓取 favicon）；自定义上传的图标不会被覆盖
- **文件日志系统（生产调试必备）**：不再依赖 print / 控制台输出。启动时在 %APPDATA%\\zhixing_workbench\\debug.log 追加写入日志：
  - 启动横幅 === ZhixingWorkbench v3.2.0 started ===
  - 关键诊断通道：[DnD]（tkdnd 版本、DLL 搜索链）、[Tray]（pystray 缺失、图标缺失）、[dock]（停靠轮询异常）、[Launch]（窗口位置越界 → 自动居中）
  - 超过 500KB 自动删除旧日志，避免无限膨胀
  - stderr 同步重定向到日志文件，未捕获异常也有迹可循

### 变更
- APP_VERSION：3.1 → 3.2.0（代码内常量 + version_info.txt + setup_installer.nsi 同步升至 3.2.0.0）
- ZhixingWorkbench.spec：console=False 启用 runw.exe 启动器（不弹 CMD）；datas 增加 tkinterdnd2/tkdnd 目录保证拖拽 DLL 正确加载
- DnD 初始化时序修复：从 WorkbenchApp.__init__ 的 after(500, _init_dnd) 改为在 Application._run_main 主窗口创建后立即同步调用 self.app._init_dnd()，解决打包环境下偶尔初始化失败导致「拖不动 / 禁止符号🚯」
- README.md 全面同步 v3.2 功能清单与构建流程（MSIX / Setup / 绿色版三条路径）
- 帮助手册.md 对应版本改为 v3.2.0，新增「拖拽导入」「刷新图标」「窗口显示修复」「文件日志」章节
- setup_installer.nsi 版本号同步 3.2.0.0

### 修复
- **主窗口不显示（任务栏预览但打不开）**：
  1. 启动时校验窗口 X/Y 是否落在所有显示器组合的可见矩形内，超出 → 强制 center_window 居中
  2. 从托盘恢复时显式依次执行 deiconify → state(normal) → attributes(-alpha 1.0) → lift → focus_force，解决 withdrawn / 透明度 0 / 最小化 三态残留叠加后的「隐身窗口」
- 拖拽时禁止符号🚯（拖不动）：确认 Tk 被 TkinterDnD monkey-patch + onedir 包含 tkdnd DLL + 注册端落到实际承载的 scroll/grid_frame
- 运行时弹出 CMD 黑窗：通过 console=False + 文件日志彻底消除对控制台子系统的依赖

---
## [3.1.0] - 2026-08-17

### 新增
- **窗口大小与位置持久化（核心）**：关闭程序时保存当前窗口几何信息到 `window_geometry`（`WxH+X+Y` 格式），下次启动自动恢复；带有效性校验：尺寸必须在 `[1100×840, 1600×1000]` 内、窗口至少 100×100 可见到屏幕内 → 否则兜底为默认 1200×860 居中
- **退出保存状态过滤**：仅当窗口为 `normal` / `zoomed` 正常展开态时写入几何信息；`withdrawn`（隐藏到托盘）、`iconified`（最小化）、停靠态（宽度 < 1100）均不保存，避免异常尺寸覆盖用户偏好

### 变更
- `APP_VERSION`：`3.0.2` → `3.1`
- `version_info.txt` / `setup_installer.nsi` → `3.1.0.0`
- README.md：设置功能行补充「窗口大小位置记忆」
- 帮助手册.md：`app_settings.json` 字段表补充 `window_geometry`

---

## [3.0.2] - 2026-08-17

### 新增
- **分类拖拽排序**：分类标签支持短按切换、长按/拖移 拖拽排序；顺序持久化写入 `category_order`；「全部」天然固定；更名开关关闭时 cursor=arrow + 不绑定拖拽（全面锁定）
- **首页欢迎条扁平化两栏重构**：左栏「问候语 + Daily Quote 每日金句（中文粗体 + 英文轻体 + 双语作者）」，右栏「Win11 风格 36px 大号蓝色时钟 + 日期」，圆角 20px
- **中英双语金句库全新重建**：40 句（28 句中国经典 + 12 句西方经典），全部校对无错句，返回 `(cn, en, bilingual_author)`；按日期种子稳定取句
- **更名开关全面生效**：修复关闭开关后卡片双击重命名、卡片右键「重命名」、导航项双击/右键重命名仍可操作的问题；修复分类管理弹窗 `_populate_cat_manager` NameError
- **全面持久化**：新增项目类型选择记忆（`last_shortcut_type`）、视图大小记忆（`last_view_size`）、分类记忆（`last_view_category`）、分类顺序（`category_order`）
- **便携模式数据目录提示**：EXE 同级 `data/` 可写 → 「更改位置/恢复默认」自动 DISABLED + 灰显 + 橙色零留痕提示条

### 变更
- `APP_VERSION`：`3.0.1` → `3.0.2`
- `APP_SLOGAN`：`致 虚 极 守 静 笃` → `致 虚 极 / 守 静 笃`（斜杠断句）
- 设置页标签「分类更名」→「更名设置」；开关描述更新
- `version_info.txt` / `setup_installer.nsi` 同步为 3.0.2.0
- README.md 功能描述全面同步（快捷启动分类拖拽、首页双语金句、设置更名设置、slogan 斜杠）

---

## [3.0.1] - 2026-08-17

### 新增
- **快捷启动分类记忆（跨会话持久化）**：切换分类时写入 app_settings.last_view_category，下次登录直接回到上次停留的分类选项卡；初始化时做有效性校验（不存在则兜底为「全部」）
- **设置 → 导航设置 → 分类更名开关**：新增 CTkSwitch「允许分类右键重命名和删除（关闭可防止误操作）」，总开关字段 category_rename_enabled 默认 True
- **便携（绿色）版数据目录提示**：启动时探测到 EXE 同级 data/ 可写（即便携模式）→ 「更改位置」「恢复默认位置」两个按钮自动 DISABLED + 灰显，并加橙色提示条「便携（绿色）版零留痕设计：数据固定在 EXE 同级 data/，不可更改」

### 修复
- **分类右键菜单 & 分类管理弹窗按钮未受控**：开关关闭时，分类标签右键菜单显示灰色「重命名（已关闭）/ 删除（已关闭）+ 引导开启路径」；管理分类弹窗列表里每行「重命名」「删除」按钮同步 state=disabled + 灰显
- **Slogan 断句**：「致 虚 极 守 静 笃」→「致 虚 极 / 守 静 笃」（斜杠断句，更符合原文节奏）

### 变更
- APP_VERSION：3.0.0 → 3.0.1
- version_info.txt：filevers / prodvers 同步为 (3, 0, 1, 0) / 3.0.1.0

### 修复（Hotfix）
- **更名开关全面生效**：修复关闭开关后卡片双击重命名、卡片右键「重命名」、导航项双击/右键重命名仍可操作的问题；修复分类管理弹窗 `_populate_cat_manager` 因 `_ren_on` 未传参导致 NameError
- **开关文案更新**：设置页标签「分类更名」→「更名设置」；开关描述改为「允许重命名操作（关闭后卡片双击/右键、分类、导航项更名均禁用）」；各处引导路径同步更新为「设置 → 导航设置 → 更名设置」
- **新增项目类型选择持久化**：对话框打开时自动恢复上次选择的类型（软件/网址/系统命令），保存时写入 `last_shortcut_type`
- **视图大小持久化**：切换「小/中/大」视图后记住选择，下次启动自动恢复，写入 `last_view_size`
- **分类拖拽排序**：分类标签支持短按切换、长按/拖移 拖拽排序；顺序写入 `category_order`；「全部」天然固定；更名开关关闭时非全部项 cursor=arrow 且不绑定拖拽（全面锁定）
- **首页欢迎条扁平化两栏重构 + 中英双语金句库**：左栏「问候语 + Daily Quote（中文粗体 + 英文轻体 + 双语作者）」，右栏「Win11 风格 36px 大号蓝色时钟 + 日期」；金句库全量校对重建 40 句（中西方各半，中英双语，无错句）

---

## [3.0.0] - 2026-08-16

### 新增
- **实时时钟**：首页欢迎栏集成 Win11 风格垂直时钟（时间上 · 日期下，精确到秒，Segoe UI Variable 字体）
- **版权信息**：侧边栏底部、关于页、登录页、设置密码页统一展示「© 2026 知行工作室」
- **进程级 + 窗口级 AppUserModelID v3**：`SetCurrentProcessExplicitAppUserModelID` + `SHGetPropertyStoreForWindow` 双保险，解决固定到任务栏显示 Python 徽标 / 名字变 Python GUI / 重 2 层图标

### 修复
- **番茄钟按钮 emoji 渲染异常**：⏸ / ▶ 在 CTk 字体栈下被错误渲染为红色数字「2」→ 改为纯中文「暂停」/「继续」（76px），右侧容器同步加宽至 140px
- **番茄钟布局重复图标**：time_label 中硬编码前置 🍅 / ☕ 与行尾按钮图标重复 → 删除前置图标，改为 `「  25:00   │   专注进行中  」` 竖线分隔 + 左右 padding 16px 呼吸感
- **初始窗口尺寸内容截断**：geometry 调整为 1200×860，minsize 1100×840，`center_window` 参数修复不再覆盖设置值
- **添加分类后错位重叠显示不全**：`_rebuild_cat_buttons()` 先 `winfo_children()` 暴力清空 + 再正确取 `info["btn"]` 双保险 destroy；`_layout_cat_buttons()` 增加中文 `min_reasonable` 宽度兜底（每字 ≥ 12px），避免测量值 32px 画 4 字导致只剩「具」
- **打包配置污染**：`ZhixingWorkbench.spec` / `version_info.txt` / `setup_installer.nsi` 被本地路径字符串误写 → 重写为标准版本，`PyInstaller --version-file` 校验通过

### 变更
- `APP_USER_MODEL_ID`：`ZhixingStudio.Workbench.v2` → `ZhixingStudio.Workbench.v3`

---

## [2.5.8] - 2026-07

### 新增
- **窗口级 AppUserModelID**：除进程级外，主窗口 + 登录窗口均通过 `SHGetPropertyStoreForWindow` 写入 AppID；NSIS 快捷方式 `System.AppUserModel.ID` 同步写入 → 三层统一，任务栏关联正确

### 修复
- 快捷方式右键「发送到」图标与真实桌面图标不同的缓存问题

---

## [2.5.5] - 2026-07

### 变更
- UI 命名统一：按钮「添加快捷方式」→「**+ 新增项目**」；弹窗「新增/编辑快捷方式」→「新增/编辑项目」
- 分类名迁移：启动时自动把数据中旧分类名 `添加快捷方式` 迁移为 `新增项目`，保持 UI 与数据一致

---

## [2.5.0] - 2026-06

### 新增
- **番茄钟 v2（PomodoroTimer 绝对时间戳版）**：不再每秒 `remaining -= 1`，改记 `_end_at = now + duration`，每次 tick 用 `time.time()` 差值得到真实剩余 → 抗锁屏 / 最小化 / 切页 / 加任务延迟
- **番茄钟完成提醒**：`winsound.Beep` 三声叮-叮-咚 + 右下角 360×170 Toast 浮窗（立即继续 / 跳过 / 延后 5 分钟 / 30 秒不操作自动继续）
- **番茄钟暂停/继续同按钮**：按钮文字在 `暂停` ↔ `继续` 间切换，按钮宽 76px

---

## [2.3.18] - 2026-05

### 新增
- **自动锁屏**：监听全局 `<Button-1> / <Key> / <Motion> / <MouseWheel>` 重置 idle 计时；每 30s tick 检查阈值（关闭 / 1 / 3 / 5 / 10 分钟）；阈值到 → `_show_lock_screen()` 显示 🔒 LockScreenFrame；若开启窗口停靠则同步 `withdraw()` 进托盘
- **侧边栏 Logo 双击锁屏**：双击顶部 Logo 区 `_logo_frame` 可手动触发锁屏
- **托盘「锁定窗口」**：托盘菜单新增锁定项，触发后回到主线程锁屏

---

## [2.3.0] - 2026-04

### 新增
- **QQ 式窗口靠边停靠**（`install_dock_feature`）：拖到左/右屏幕边缘 ≤ 14px + 鼠标离开窗口 400ms → 收为 6px 窄边；鼠标碰到收起边 180ms → 展开；拖离 28px 外 → 取消停靠；支持开关读取（`get_auto_dock_enabled`）与关闭时瞬时复位
- **导航拖拽**：首页 / 设置 / 关于为固定项，其余导航项支持鼠标拖拽排序（开关 `get_nav_drag_enabled`，默认开启）
- **系统托盘（pystray）**：关闭窗口自动 `withdraw()` 进托盘；图标使用 Z 字符样式；菜单：显示主窗口 / 锁定窗口 / 退出
- **安装版 + 便携版双模式数据目录**：便携版启动时检测到安装版 `~/.zhixing_workbench/` 有数据 → 询问并合并迁移

---

## [2.0.0] - 2026-03

### 新增
- **首次启动自定义密码设置**（SetupPasswordFrame）：「欢迎使用知行工作台」引导页，两次输入 ≥ 6 位密码 → 保存为 password_hash（PBKDF2-SHA256）并写入 created_at；无默认密码
- **密码登录界面**（LoginFrame）：已有密码状态下启动弹出，校验通过后 `config.unlock()` 解密 enc_data
- **数据加密存储**：登录后敏感数据（todos / notes / shortcuts）以 AES 流式加密写入 enc_data；未登录状态下临时数据明文保存（保证关机不丢），下次登录后自动加密合并
- **设置页面修改密码**：需输入当前密码 + 新密码（≥ 6 位）+ 确认新密码
- **快捷启动**：项目类型「软件 / 网址 / 系统命令」三单选；分类标签栏右键「重命名 / 删除」+ ⚙ 管理分类弹窗；系统预设一键导入（devmgmt.msc / diskmgmt.msc 等管理工具）；卡片图标自动从 exe / 系统命令 / 网址 favicon 提取（Z 字符兜底）
- **待办事项**：任务增删改查 / 完成切换 / 优先级（high / normal / low）/ 创建时间
- **笔记记录**：笔记增删改 / 标题 + 内容 / 创建时间 / 按时间排序
- **主题切换**：深色 / 浅色 / 跟随系统（SegmentedButton 切换，写入 config.theme）
- **关于页**：Logo / 版本 / 标语 / 功能列表 / 检查更新按钮
- **NSIS 安装包**：Setup.exe，支持开始菜单 + 桌面快捷方式，快捷方式写入 AppUserModelID

---

## [1.0.0] - 2026-02

### 新增
- 项目初始化：CustomTkinter 脚手架、侧边栏 + 内容区双栏布局、基础主题色板
