# macOS 聊天软件自动化控制平台

基于最新的 Python 3.12 工程化与 `uv` Workspace（Monorepo）特性构建的 macOS 微信 / 企业微信自动化基础设施工程。

完全基于 macOS 底层原生 **Accessibility API (无障碍辅助功能)** 结合 **PyObjC / Quartz** 框架重新打造。实现了界面缩放无关、分辨率无感知的纯 Native 级 UI 节点遍历与交互。

---

## 🏗️ 架构设计 (Monorepo)

系统基于标准的 `Workspace` 拓展，划分为高内聚、低耦合的“一核两翼一顶”结构：

```text
mac/
├── pyproject.toml               # Workspace 全局工作区依赖管理
├── .env                         # API 层基础环境变量配置
│
├── packages/                    # 📦 底层 & 业务能力层
│   ├── ax-core/                 # ⚙️ MacOS 辅助功能核心驱动层
│   ├── wechat-agent/            # 🟢 微信业务能力 Agent
│   └── wework-agent/            # 🔵 企业微信业务能力 Agent
│
└── apps/                        # 🚀 上层应用网关
    └── automation-api/          # 🌐 统一 FastAPI 中枢服务器
```

### 1. `packages/ax-core` (底层无障碍驱动)

提供抽象且强韧的底层接口交互：

- **`__init__.py`**：深入 PyObjC 获取被包裹的 `AXValueRef` 等指针属性数据，提供通用的 UI 树遍历搜索 `walk` 算法抽象，快速精准地获取列表、对话框等控件抽象节点。
- **`input.py`**：混合软硬件级键鼠模拟，针对拦截权限较严的搜索浮窗采用系统级 `osascript` 唤起特权按键（Return/Tab），针对高频纯修饰符行为（如选中全选 `Cmd+a`）采用极速地 `Quartz.CGEvent` 协程投递。

### 2. `packages/wechat-agent` & `packages/wework-agent` (双端业务模型)

各自独立封装对应的平台逻辑（基于 Bundle ID 和 AX 树结构）：

- `_activate()`：拉起并激活指定软件到前台。
- `list_sessions()`：提取软件左侧会话栏最新对话列表数据。
- `send_by_title()`：完成从开启搜索浮窗、写入检索词、选中对应高亮联系人，进入对话流后确认并自动粘贴投递的完整无障碍链路。
- 两个包分别对外暴露了 CLI 运行命令 `send-wechat` 和 `send-wework` 供测试快速调用。

### 3. `apps/automation-api` (通用 HTTP 网关)

标准且强壮的 FastAPI 的上层宿主：

- **API Router**：暴露独立的 `http://localhost:8200/wework/*` 与 `/wechat/*` HTTP 接口集合。
- **Pydantic Schemas**：强类型约束 Request 与 Response 消息体，自动生成 OpenAPI/Swagger UI 文档。
- **依赖注入并发锁 (`OperationLockDep`)**：基于 `asyncio.Lock()` 的注入挂载。由于 macOS 操作系统 UI 级输入输出是独占且局部的，网关在遇到并发的高 QPS 发信请求时，能够精准地转为串行状态机，防范鼠标指针和焦点互相干扰或漂移。
- **服务自检与安全拦截**：提供了 `/health` 端点探测底层的系统级授权，并可通过包含预置鉴权的 `ApiKeyDep` 依赖隔离不受信的网络攻击。

---

## 🛠️ 安装与运行

### 1. 环境准备

项目基于 `uv` 工具进行闪电般的管理。请确保操作系统中安装了 `uv` （支持 Python 3.12+）。
首次使用前必须让当前执行命令所在的终端 App（如 iTerm2, Alacritty, Terminal 等）在“系统设置 -> 隐私与安全性 -> 辅助功能”中开启授权。

### 2. 构建依赖

在项目根目录（`mac/`）执行：

```bash
uv sync
```

依赖会自动跨所有的 App 与 Package 完成精准解析、下载与工作区软链安装。

### 3. 独立脚本运行模式

如果你无需开启 HTTP 后台，只想通过命令行作为工具来控制发包（会自动唤起对应的主程序），你可以直接使用封装好的命令：

```bash
# 测试企业微信
uv run send-wework "某某某" "纯自动化测试消息：Hello WeCom"

# 测试微信
uv run send-wechat "文件传输助手" "纯自动化测试消息：Hello WeChat"
```

### 4. 启动后端 HTTP 服务模式

若需供外部系统、群发脚本、客服机器人集群调度，可启动 API 中控服务器：

```bash
uv run automation-server
```

- 服务将根据 `.env` 配置默认开启于 `http://localhost:8200`
- 进入 `http://localhost:8200/docs` 查看具备完整参数提示的 Swagger 可视化接口调试平台。

#### 发信示例：

```bash
curl -X POST "http://localhost:8200/wework/send_by_title" \
     -H "Content-Type: application/json" \
     -d '{"title": "张三", "message": "通过 HTTP 中枢网关发送企微自动化消息"}'
```
