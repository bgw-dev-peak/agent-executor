# Agent Executor — 工作流角色说明文档

**项目:** Claude CLI HTTP Wrapper Service (`server.py`)
**日期:** 2026-03-23
**用途:** 描述从需求到上线的完整过程，每个阶段对应一个独立角色，后续可按此结构创建自动化工作流。

---

## 角色总览

```
需求输入
   │
   ▼
[角色 1: 分析师]  → 理解问题，定义边界
   │
   ▼
[角色 2: 架构师]  → 做技术决策，输出设计
   │
   ▼
[角色 3: 工程师]  → 按设计编写代码
   │
   ▼
[角色 4: 测试员]  → 执行测试用例
   │
   ▼
[角色 5: 校验员]  → 验收，确认上线标准达成
```

---

## 角色 1 — 分析师 (Analyst)

**职责:** 理解需求，识别约束，定义问题边界。输出内容供架构师使用。

### 思考过程

1. **原始需求是什么？**
   - 需要一个方式让 CI 管道、cron 任务、Shell 脚本等能通过 HTTP 触发 Claude。
   - 调用者不想管理 API Key，希望复用本地已登录的 `claude` CLI。

2. **核心问题是什么？**
   - 如何将命令行工具（`claude -p "..."`）暴露为 HTTP 接口。
   - 如何处理 PTY 输出（claude CLI 在非 TTY 环境下不输出内容）。
   - 如何处理超时和错误状态。

3. **约束识别**
   - 运行在本地/内网，不需要认证。
   - 调用者是脚本，期望同步响应（不接受异步轮询）。
   - 保持服务极简，不引入不必要依赖。

4. **不在范围内**
   - 流式输出（SSE/WebSocket）。
   - 持久化任务队列。
   - 多用户认证。
   - Docker 打包（当前阶段）。

### 输出物
- 需求边界文档（参见 `docs/brainstorms/2026-03-22-claude-http-service-brainstorm.md`）
- 核心 API 草图：`POST /run`、`GET /health`

---

## 角色 2 — 架构师 (Architect)

**职责:** 根据分析师输出做技术选型，输出可执行的设计方案。

### 决策过程

#### 决策 1：HTTP 框架

| 选项 | 优点 | 缺点 | 决定 |
|------|------|------|------|
| FastAPI | 自动文档、异步原生、最少样板 | 需要安装依赖 | 初始备选 |
| `http.server` (stdlib) | 零依赖、无安装步骤 | 无自动文档 | **选用** |

**理由:** 项目目标是极简可运行，stdlib 方案无需 `pip install`，更符合自动化场景中一键启动的需求。

#### 决策 2：Claude 执行方式

| 选项 | 优点 | 缺点 | 决定 |
|------|------|------|------|
| 直接调用 Anthropic API | 更可控 | 需要单独管理 API Key | 否 |
| subprocess 调用 `claude` CLI | 复用本地认证和配置 | 需要 PTY 才能产生输出 | **选用** |

**关键发现:** `claude` CLI 在非 TTY 环境（标准 subprocess）下不产生任何输出。必须使用 `pty.openpty()` 模拟终端。

#### 决策 3：响应模式

| 选项 | 适用场景 | 决定 |
|------|----------|------|
| 异步（返回 job_id，客户端轮询）| 长任务、并发高 | 否 |
| 同步（阻塞等待全部输出）| 脚本化调用 | **选用** |

**理由:** 脚本调用方的最简心智模型：发请求 → 等响应 → 拿结果。

#### 决策 4：输出清洗

claude CLI 输出包含 ANSI/VT100 转义序列（颜色、光标控制、OSC 序列）。需要正则清洗后才能返回纯文本。

```
正则: \x1b(?:\][^\x07\x1b]*[\x07\x1b]|\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])
```

顺序重要：OSC 序列（`\x1b]...`）必须在单字符 catch-all 之前匹配，否则残留字符污染输出。

#### 最终架构图

```
HTTP 客户端
    │  POST /run {"prompt": "..."}
    ▼
HTTPServer (stdlib)
    │
    ▼
Handler.do_POST()
    │  验证 JSON body，提取 prompt
    ▼
run_claude(prompt)
    │  pty.openpty() → subprocess Popen
    │  select() 循环读取 master_fd
    │  deadline 检测超时
    ▼
ANSI 清洗 → 纯文本
    │
    ▼
{"output": "..."}  HTTP 200
```

#### 错误码映射

| 情况 | HTTP 状态 | body |
|------|-----------|------|
| 成功 | 200 | `{"output": "..."}` |
| JSON 解析失败 | 400 | `{"error": "invalid JSON body"}` |
| prompt 为空 | 400 | `{"error": "'prompt' field is required"}` |
| claude 不在 PATH | 500 | `{"error": "claude CLI not found in PATH"}` |
| claude 返回非 0 | 500 | `{"error": "<stderr>"}` |
| 超时 | 504 | `{"error": "claude timed out after 300s"}` |

### 输出物
- 架构设计（本节）
- API 规范（见上表）
- 关键技术决策记录（ADR）

---

## 角色 3 — 工程师 (Engineer)

**职责:** 按架构设计编写代码，遵循最小实现原则。

### 实现过程

#### 步骤 1：PTY 核心函数

```python
# server.py: run_claude(prompt) — 核心实现
master_fd, slave_fd = pty.openpty()
proc = subprocess.Popen(
    ["claude", "-p", prompt, "--dangerously-skip-permissions"],
    stdout=slave_fd, stderr=slave_fd, stdin=subprocess.DEVNULL,
    env=env,  # 去除 CLAUDECODE 环境变量，避免递归
)
os.close(slave_fd)  # 主进程关闭 slave 端，否则 EOF 不会触发
```

**关键细节:**
- `slave_fd` 在 `Popen` 后必须立即关闭，否则 `master_fd` 永远不会收到 EOF。
- 从环境变量中移除 `CLAUDECODE`，防止服务被 claude 识别为子进程而改变行为。

#### 步骤 2：select 读取循环

```python
while True:
    remaining = deadline - time.time()
    r, _, _ = select.select([master_fd], [], [], min(remaining, 1.0))
    if r:
        chunk = os.read(master_fd, 4096)
        ...
    if proc.poll() is not None:
        # 进程结束后继续 drain 剩余输出
        ...
        break
```

**关键细节:**
- `select` 超时设为 `min(remaining, 1.0)` — 保证既不无限阻塞，又能精确感知总超时。
- 进程退出后需要额外 drain 循环，避免最后几个 chunk 丢失。

#### 步骤 3：ANSI 清洗

```python
_ANSI_RE = re.compile(
    r"\x1b(?:\][^\x07\x1b]*[\x07\x1b]|\[[0-?]*[ -/]*[@-~]|[@-Z\\-_])"
)
clean = _ANSI_RE.sub("", raw).replace("\r\n", "\n").replace("\r", "\n").strip()
```

#### 步骤 4：HTTP Handler

```python
class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # 读取 Content-Length → json.loads → 提取 prompt → run_claude → send_json
```

#### 步骤 5：启动入口

```python
parser.add_argument("--port", type=int, default=8086)
parser.add_argument("--host", default="127.0.0.1")
server = HTTPServer((args.host, args.port), Handler)
server.serve_forever()
```

### 实现检查清单

- [x] PTY 打开/关闭成对处理（finally 块）
- [x] slave_fd 在 Popen 后立即关闭
- [x] 超时后 kill + wait 防止僵尸进程
- [x] ANSI 正则顺序正确（OSC 在前）
- [x] 所有错误路径均有对应 HTTP 状态码
- [x] 服务启动时打印监听地址和接口提示

---

## 角色 4 — 测试员 (Tester)

**职责:** 设计并执行测试用例，验证功能正确性。

### 测试过程

#### 环境准备

```bash
# 确认 claude CLI 可用
claude --version

# 启动服务（后台运行）
python3 server.py --port 8086 &
SERVER_PID=$!

# 等待服务就绪
sleep 1
```

#### 用例 T-01：健康检查

```bash
curl -s http://127.0.0.1:8086/health
# 期望: {"status": "ok"}
```

#### 用例 T-02：正常 prompt

```bash
curl -s -X POST http://127.0.0.1:8086/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "say the word HELLO and nothing else"}'
# 期望: {"output": "HELLO"} 或包含 HELLO 的文本
```

#### 用例 T-03：空 prompt（400）

```bash
curl -s -X POST http://127.0.0.1:8086/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": ""}'
# 期望: {"error": "'prompt' field is required"}  HTTP 400
```

#### 用例 T-04：非法 JSON（400）

```bash
curl -s -X POST http://127.0.0.1:8086/run \
  -H "Content-Type: application/json" \
  -d 'not-json'
# 期望: {"error": "invalid JSON body"}  HTTP 400
```

#### 用例 T-05：未知路由（404）

```bash
curl -s http://127.0.0.1:8086/unknown
# 期望: {"error": "not found"}  HTTP 404
```

#### 用例 T-06：输出无 ANSI 污染

```bash
OUTPUT=$(curl -s -X POST http://127.0.0.1:8086/run \
  -H "Content-Type: application/json" \
  -d '{"prompt": "print the number 42"}')
echo "$OUTPUT" | python3 -c "
import sys, json
out = json.load(sys.stdin)['output']
assert '\x1b' not in out, 'ANSI escape found in output'
print('PASS: no ANSI escapes')
"
```

#### 清理

```bash
kill $SERVER_PID
```

### 测试矩阵

| 用例 | 输入 | 期望 HTTP | 期望 body | 状态 |
|------|------|-----------|-----------|------|
| T-01 | GET /health | 200 | `{"status":"ok"}` | |
| T-02 | 正常 prompt | 200 | 含 output 字段 | |
| T-03 | 空 prompt | 400 | error 字段 | |
| T-04 | 非法 JSON | 400 | error 字段 | |
| T-05 | 未知路由 | 404 | error 字段 | |
| T-06 | ANSI 清洗 | 200 | output 无 `\x1b` | |

---

## 角色 5 — 校验员 (Validator)

**职责:** 独立于工程师视角，逐条验收上线标准，给出 Go/No-Go 结论。

### 校验过程

#### 功能验收

- [ ] `GET /health` 返回 200 + `{"status":"ok"}`
- [ ] `POST /run` 返回 claude 实际文本输出
- [ ] 错误路径均有明确 HTTP 状态码（400/404/500/504）
- [ ] 输出中无 ANSI 转义残留

#### 稳定性验收

- [ ] 服务在 claude 超时（> 300s）后正常恢复，不崩溃
- [ ] 多次连续请求后无文件描述符泄漏（`lsof -p <pid> | wc -l` 稳定）
- [ ] `KeyboardInterrupt` 正常退出，打印 "Stopped."

#### 安全验收

- [ ] 默认绑定 `127.0.0.1`（不对外网暴露）
- [ ] prompt 直接传入 CLI 参数列表（非 shell 拼接，无命令注入风险）
- [ ] 无硬编码凭据

#### 可观测性验收

- [ ] 每个请求打印客户端 IP + 方法 + 路径到 stdout
- [ ] 启动时打印监听地址和可用接口

#### 上线判定

| 维度 | 标准 | 结果 |
|------|------|------|
| 功能完整 | 所有 T-01~T-06 通过 | |
| 无崩溃 | 超时/错误均有处理 | |
| 安全 | 本地绑定 + 无注入 | |
| 可观测 | 日志可读 | |

**Go 条件:** 所有行均通过。任意一行 Fail 则 No-Go，记录原因并回传给工程师。

---

## 工作流编排参考

以下是将上述 5 个角色组合成自动化工作流的参考结构：

```yaml
# workflow: feature-delivery.yaml (示意)

stages:
  - name: analysis
    role: Analyst
    input: user_request
    output: requirements_doc
    trigger: new_feature_request

  - name: design
    role: Architect
    input: requirements_doc
    output: design_doc, adr
    trigger: requirements_approved

  - name: implementation
    role: Engineer
    input: design_doc
    output: source_code, checklist
    trigger: design_approved

  - name: testing
    role: Tester
    input: source_code
    output: test_results
    trigger: implementation_complete
    steps:
      - start_service
      - run_test_matrix (T-01 ~ T-06)
      - stop_service

  - name: validation
    role: Validator
    input: test_results, source_code
    output: go_no_go_decision
    trigger: testing_complete
    gate: all_checks_pass → deploy
          any_check_fail  → back_to_engineer
```

---

## 附录：关键文件索引

| 文件 | 角色 | 说明 |
|------|------|------|
| `docs/brainstorms/2026-03-22-claude-http-service-brainstorm.md` | 分析师 | 需求与决策记录 |
| `docs/workflow-roles.md` | 全体 | 本文档，工作流角色说明 |
| `server.py` | 工程师 | 核心实现（HTTP wrapper + PTY runner） |
