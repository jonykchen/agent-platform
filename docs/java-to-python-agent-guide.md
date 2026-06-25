# Java>Python Agent 开发迁移指南
---

## 1. 开发环境与工具链：Maven/Gradle → uv

### 1.1 包管理对照

| 概念 | Java | Python (本项目) |
|------|------|-----------------|
| 依赖声明 | `pom.xml` / `build.gradle` | `pyproject.toml` |
| 锁文件 | 无（Maven）/ `gradle.lock` | `uv.lock` |
| 仓库 | Maven Central | PyPI |
| 安装依赖 | `mvn install` | `uv sync` |
| 添加依赖 | 手动编辑 pom.xml | `uv add fastapi` |
| 运行 | `mvn spring-boot:run` | `uv run uvicorn app.main:app` |
| 测试 | `mvn test` | `uv run pytest` |
| 格式化 | 无内置 | `uv run ruff format` |
| Lint | Checkstyle / SpotBugs | `uv run ruff check` |
| 类型检查 | 编译器 | `uv run mypy` |

### 1.2 uv 常用命令速查

```bash
# ─── 项目初始化 ───
cd services/orchestrator-python
uv sync                          # 安装所有依赖（等价 mvn install）

# ─── 日常开发 ───
uv run uvicorn app.main:app --reload   # 启动开发服务器（热重载）
uv run pytest tests/ -v                # 运行测试
uv run pytest tests/unit/test_xxx.py -v  # 运行单个测试
uv run ruff check app/                  # Lint 检查
uv run ruff format app/                 # 格式化
uv run mypy app/                        # 类型检查

# ─── 依赖管理 ───
uv add httpx                    # 添加依赖（自动更新 pyproject.toml + uv.lock）
uv add --dev pytest-cov         # 添加开发依赖
uv remove httpx                 # 移除依赖

# ─── 直接运行脚本 ───
uv run python scripts/xxx.py    # 在项目虚拟环境中运行脚本
```

### 1.3 虚拟环境

Python 项目使用**虚拟环境**隔离依赖，类似于 Java 中每个项目有自己的 classpath：

```bash
# uv sync 时自动创建 .venv/ 目录（等价 Java 项目的 target/）
# 无需手动激活，uv run 自动使用

# 如果需要在 IDE 外手动操作：
.venv\Scripts\activate          # Windows 激活
source .venv/bin/activate       # Linux/Mac 激活
deactivate                      # 退出
```

> **与 Java 的关键区别**：Java 依赖在 `pom.xml` 声明后由 Maven 下载到 `~/.m2` 全局仓库；Python 依赖安装在项目级 `.venv/` 目录下，项目间完全隔离。

### 1.4 Python 项目目录结构 vs Maven

```
Java Maven 项目                     Python 项目（本项目）
───────────────                     ─────────────────
src/                                app/                    # 等价 src/main/java
  main/                               __init__.py           # 包标识（空文件）
    java/com/example/                  api/                  # 等价 controller
      controller/                       v1/
        OrderController.java              chat.py           # 等价 Controller 类
      service/                         core/                 # 等价 config/utils
        OrderService.java                config.py          # 等价 @Configuration
      repository/                        exceptions.py      # 等价 @ControllerAdvice
        OrderRepository.java             constants.py      # 等价 常量类
      entity/                         graph/                # Agent 状态机
        Order.java                       state.py           # 状态定义
      dto/                              builder.py         # 图构建
        OrderVO.java                    nodes/             # 各节点
    resources/                        memory/               # 状态持久化
      application.yml                 tools/                # 工具客户端
  test/                               infrastructure/       # 数据库、gRPC
    java/                           tests/                  # 等价 src/test
      OrderServiceTest.java           unit/                # 单元测试
pom.xml                               integration/        # 集成测试
                                    pyproject.toml          # 等价 pom.xml
```

**关键差异**：
- Python **没有** `public class` 包裹，一个 `.py` 文件就是一个模块
- `__init__.py` 标识目录为 Python 包（类似 Java 的 `package-info.java`，但可包含代码）
- Python 无需一个类对应一个文件，一个文件可包含多个类/函数

---

## 2. Python 语言核心特性速通

> 本章覆盖 Java 中不存在或差异巨大的语言特性，**必须掌握**才能阅读和编写本项目代码。

### 2.1 装饰器（Decorator）

装饰器是 Python 最核心的特性之一，**本项目代码中大量使用**（`@router.get`、`@app.exception_handler`、`@pytest.mark.asyncio` 等）。

**Java 思维理解**：装饰器 ≈ 注解 + AOP 切面，但装饰器是**运行时高阶函数**，远比 Java 注解灵活。

```java
// Java: 注解 + AOP（编译/加载时织入）
@Slf4j                           // Lombok 注解
@Transactional                    // Spring AOP 切面
@GetMapping("/orders/{id}")       // Spring MVC 路由映射
```

```python
# Python: 装饰器是函数，接收一个函数并返回新函数
@router.get("/orders/{order_id}")    # 等价 @GetMapping
async def get_order(order_id: int):
    ...

# 等价于：
# get_order = router.get("/orders/{order_id}")(get_order)
```

**自定义装饰器**（本项目风格）：

```python
from functools import wraps
import structlog

logger = structlog.get_logger()

# 装饰器定义：等价 Java 的 AOP 切面
def with_retry(max_retries: int = 3):
    """重试装饰器 - 等价 Spring @Retryable"""
    def decorator(func):
        @wraps(func)  # 保留原函数签名（重要！）
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    logger.warning("retry_attempt", func=func.__name__, attempt=attempt + 1)
            raise last_error
        return wrapper
    return decorator

# 使用
@with_retry(max_retries=3)
async def call_toolbus(tool_name: str):
    ...
```

**常见装饰器映射**：

| Java | Python (本项目) | 用途 |
|------|-----------------|------|
| `@GetMapping` | `@router.get()` | 路由 |
| `@PostMapping` | `@router.post()` | 路由 |
| `@Autowired` | `Depends()` | 依赖注入 |
| `@Transactional` | `@with_transaction` (自定义) | 事务 |
| `@Retryable` | `@with_retry()` (自定义) | 重试 |
| `@Slf4j` | `logger = structlog.get_logger()` | 日志 |
| `@Override` | 无需（Python 无方法重写约束） | — |

### 2.2 上下文管理器（Context Manager）

**Java 思维理解**：`with` 语句 ≈ `try-with-resources`，但更灵活。

```java
// Java: try-with-resources
try (Connection conn = dataSource.getConnection();
     PreparedStatement ps = conn.prepareStatement(sql)) {
    // 使用资源
}  // 自动关闭
```

```python
# Python: with 语句
async with db_connection() as conn:
    result = await conn.execute(query)
# 自动关闭/释放

# 本项目大量使用：信号量、锁、HTTP 客户端
async with model_semaphore:              # 并发控制
    response = await llm.ainvoke(msgs)

async with httpx.AsyncClient() as client:  # HTTP 连接池
    resp = await client.post(url, json=data)

async with asyncio.Lock():               # 协程锁
    # 临界区
```

**自定义上下文管理器**（本项目风格）：

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_db_session():
    """数据库会话上下文 - 等价 Spring @Transactional"""
    session = await create_session()
    try:
        yield session        # yield 前是 __aenter__，yield 后是 __aexit__
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()

# 使用
async with get_db_session() as session:
    result = await session.execute(query)
```

### 2.3 推导式（Comprehension）

**Java 思维理解**：推导式 ≈ Stream API 的简洁写法，但语法更紧凑。

```java
// Java: Stream API
List<String> names = orders.stream()
    .filter(o -> o.getStatus().equals("shipped"))
    .map(Order::getOrderNo)
    .collect(Collectors.toList());

Map<String, List<Order>> grouped = orders.stream()
    .collect(Collectors.groupingBy(Order::getStatus));
```

```python
# Python: 推导式（更简洁，更 Pythonic）
names = [o["order_no"] for o in orders if o["status"] == "shipped"]

# 字典推导式
grouped = {}
for o in orders:
    grouped.setdefault(o["status"], []).append(o)
# 或
from collections import defaultdict
grouped = defaultdict(list)
for o in orders:
    grouped[o["status"]].append(o)

# 集合推导式
statuses = {o["status"] for o in orders}  # 等价 orders.stream().map(...).collect(Collectors.toSet())

# 字典推导式
order_map = {o["id"]: o for o in orders}   # 等价 Collectors.toMap(Order::getId, Function.identity())
```

**本项目实际使用**：
```python
# state.py 中的初始化
tool_calls: list[dict]       # 就是 List<Map<String, Object>>
tool_results: list[dict]     # 就是 List<Map<String, Object>>

# 节点中转换结果
vo_list = [convert_to_vo(e) for e in entities]    # 等价 stream().map().collect()
valid_calls = [c for c in calls if c.get("name")]  # 等价 stream().filter().collect()
```

### 2.4 生成器（Generator）

**Java 思维理解**：生成器 ≈ `Stream.iterate` / `Iterator`，但惰性求值更彻底。

```java
// Java: Iterator / Stream
Stream.iterate(0, n -> n + 1).limit(10).forEach(System.out::println);
```

```python
# Python: 生成器函数（yield 关键字）
def count_up(max_val):
    n = 0
    while n < max_val:
        yield n    # 暂停执行，返回值；下次调用从这继续
        n += 1

for i in count_up(10):
    print(i)

# 生成器表达式（惰性求值，不占内存）
total = sum(x * x for x in range(1000000))  # 不会创建百万元素列表
```

**本项目实际使用** — LLM 流式输出：
```python
# SSE 流式响应
async def stream_chat(request: ChatRequest):
    async for chunk in llm.astream(messages):  # 生成器：逐 token 输出
        yield f"data: {chunk.content}\n\n"      # SSE 格式
    yield "data: [DONE]\n\n"
```

### 2.5 解包与星号表达式

```java
// Java: 无直接等价（需要手动处理）
public void process(String first, String[] rest) { ... }
```

```python
# Python: 解包（极其常用）
# 列表解包
first, *rest = [1, 2, 3, 4]   # first=1, rest=[2, 3, 4]
first, *_, last = [1, 2, 3, 4]  # first=1, last=4, _=[2, 3] 丢弃中间

# 字典解包
defaults = {"timeout": 30, "retries": 3}
overrides = {"timeout": 60}
config = {**defaults, **overrides}  # config = {"timeout": 60, "retries": 3}
# 等价 Java: new HashMap<>(defaults); config.putAll(overrides);

# 函数参数解包
def execute_tool(name: str, arguments: dict, **kwargs):  # **kwargs 接收任意关键字参数
    ...

opts = {"timeout": 60, "async_mode": True}
execute_tool("query", {"order_id": "123"}, **opts)  # 展开 opts 为关键字参数

# 本项目中 LangGraph 状态合并就是这个原理：
# new_state = {**old_state, **returned_updates}
```

### 2.6 f-string 格式化

```java
// Java: String.format / StringBuilder
String msg = String.format("订单 %s 状态: %s", orderId, status);
```

```python
# Python: f-string（最常用，性能好，可读性强）
msg = f"订单 {order_id} 状态: {status}"
msg = f"计算结果: {2 ** 10}"              # 可内嵌表达式
msg = f"结果: {result:.2f}"               # 格式化浮点
msg = f"用户: {user['name']}"             # 访问字典
msg = f"步骤: {state['step_count'] + 1}"  # 内嵌运算
```

### 2.7 类型提示进阶

```java
// Java: 泛型 + 通配符
List<? extends Order> orders;
Map<String, List<Order>> grouped;
Optional<Order> findOrder(Long id);
```

```python
# Python: 类型提示（3.12+ 语法，本项目使用）
from typing import Annotated, Any

# 基本类型
def process(name: str, count: int, ratio: float, active: bool) -> str: ...

# 容器类型（Python 3.12+ 直接用小写）
def get_orders() -> list[dict[str, Any]]: ...        # List<Map<String, Object>>
def get_config() -> dict[str, str | int]: ...        # Map<String, String|Integer>

# 可选类型
def find_order(id: int) -> Order | None: ...         # 等价 Optional<Order>

# 回调/函数类型
from collections.abc import Callable
Handler = Callable[[AgentState], dict]                # 等价 Function<State, Map>

# Annotated：类型 + 元数据（Pydantic/LangGraph 大量使用）
from pydantic import Field

class OrderRequest(BaseModel):
    order_no: str = Field(..., min_length=1, max_length=64, description="订单号")
    #      ↑ 类型    ↑ 校验规则（等价 @NotBlank @Size(max=64) @Column(length=64)）

# TypedDict：固定结构的字典类型（LangGraph AgentState 使用）
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]   # 类型 + reducer 行为
    step_count: int
```

### 2.8 Python 数据结构 vs Java Collections

| Java | Python | 说明 |
|------|--------|------|
| `ArrayList<T>` | `list` | `orders = []` / `orders.append(o)` |
| `HashMap<K,V>` | `dict` | `config = {}` / `config["key"] = val` |
| `HashSet<T>` | `set` | `ids = {1, 2, 3}` / `ids.add(4)` |
| `LinkedList<T>` | `collections.deque` | 队列场景 |
| `TreeMap<K,V>` | 无内置 | 用 `dict` + `sorted()` |
| `ConcurrentHashMap` | 无直接等价 | asyncio 单线程无需并发容器 |
| `Collections.unmodifiableList()` | `tuple` | `orders = ("a", "b")` 不可变 |
| `Optional.ofNullable(x)` | `x if x is not None else default` | — |

**常用操作对照**：

```java
// Java
list.add(item);                          // 追加
list.get(0);                             // 按索引取值
list.size();                              // 长度
map.getOrDefault("key", defaultValue);   // 带默认取值
map.containsKey("key");                   // 判断存在
map.put("key", value);                    // 设置
String val = map.get("key");              // 取值（可能 null）
```

```python
# Python
list.append(item)                        # 追加
list[0]                                  # 按索引取值
len(list)                                # 长度
dict.get("key", default_value)           # 带默认取值
"key" in dict                            # 判断存在
dict["key"] = value                      # 设置
val = dict["key"]                        # 取值（不存在抛 KeyError）
val = dict.get("key")                    # 取值（不存在返回 None）
```

### 2.9 Java→Python 语法速查卡

> 以下每个点都对应一个 Java 工程师初次读 Python 代码时的"这是什么？"时刻。

#### `self` 参数：显式的 `this`

```java
// Java: this 是隐式的
public class OrderService {
    private OrderRepository repo;
    
    public Order findOrder(Long id) {
        return this.repo.findById(id);  // this 可省略
    }
}
```

```python
# Python: self 是显式的，且必须作为第一个参数
class OrderService:
    def __init__(self, repo: OrderRepository):   # self = this
        self.repo = repo                          # self.repo = this.repo
    
    async def find_order(self, order_id: int) -> Order | None:
        return await self.repo.find_by_id(order_id)  # self 不可省略
```

**关键规则**：
- 实例方法的**第一个参数永远是 `self`**（名称约定，不是关键字，但绝不要改名）
- `self` 在调用时**自动传入**，不需要手动写：`service.find_order(1)` 而非 `service.find_order(self, 1)`
- `self.xxx` 等价 Java 的 `this.xxx`，但 Python **必须显式写 `self.`**，不能省略

#### 没有 `new` 关键字

```java
// Java: 必须用 new 创建对象
OrderService service = new OrderService(repo);
List<String> names = new ArrayList<>();
```

```python
# Python: 直接调用类名（类就是可调用的工厂函数）
service = OrderService(repo)
names = []               # 内置类型用字面量语法
names = list()           # 等价写法
config = Settings()      # 等价 new Settings()
```

#### `if __name__ == "__main__"`：Python 的入口点

```java
// Java: main 方法是入口
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
```

```python
# Python: 模块可以被导入，也可以直接运行
# 这行判断"是直接运行的还是被导入的"

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000)

# 被导入时 __name__ == "app.main"，不执行
# 直接运行时 __name__ == "__main__"，执行
```

**本项目不使用此模式**（通过 `uv run uvicorn` 启动），但第三方库的 `__main__.py` 会用到，了解即可。

#### 命名规范：snake_case 革命

| Java 命名 | Python 命名 | 示例 |
|-----------|------------|------|
| `ClassName` (PascalCase) | `ClassName` (PascalCase) | `OrderService` |
| `methodName()` (camelCase) | `method_name()` (snake_case) | `find_order()` |
| `fieldName` (camelCase) | `field_name` (snake_case) | `order_no` |
| `CONSTANT_NAME` (UPPER_SNAKE) | `CONSTANT_NAME` (UPPER_SNAKE) | `MAX_STEPS` |
| `packageName` (全小写) | `module_name` (全小写) | `tool_bus_client` |
| `SimpleName.java` | `simple_name.py` | `chat_request.py` |

**本项目文件命名对照**：

```
Java 风格命名                    本项目 Python 实际命名
──────────────                    ────────────────────
OrderService.java         →      order_service.py (如果用类)
                                    或模块级函数
ChatRequest.java         →      schemas.py 中 class ChatRequest(BaseModel)
AgentState.java          →      state.py 中 class AgentState(TypedDict)
ToolBusClient.java       →      tool_bus_client.py
```

> **注意**：Pydantic `BaseModel` 类名本身用 PascalCase（如 `ChatRequest`），但字段名用 snake_case（如 `order_no`）。Pydantic 默认自动将 snake_case 字段序列化为 camelCase（可通过 `alias` 配置）。

#### 多返回值：元组解包

```java
// Java: 需要包装类或 Map 返回多个值
public class Result {
    private boolean success;
    private String data;
}
Result result = process();
```

```python
# Python: 直接返回多个值（实际是元组）
def process() -> tuple[bool, str]:
    return True, "ok"

# 解包接收
success, data = process()

# 本项目实际使用
async def thinking_node(state: AgentState) -> dict:   # 返回更新字典
    return {"current_step": "tool_call", "tool_calls": [...]}

# 忽略不需要的返回值
success, _ = process()      # _ 是约定，表示"不关心这个值"
```

#### `@property`：Python 的 getter/setter

```java
// Java: getter/setter
public class Order {
    private String status;
    public String getStatus() { return status; }
    public void setStatus(String status) { this.status = status; }
}
```

```python
# Python: 直接访问属性，需要拦截时用 @property
class Order:
    def __init__(self):
        self._status = "pending"   # _ 前缀表示"私有"（约定，不强制）
    
    @property                       # getter（等价 getStatus()）
    def status(self) -> str:
        return self._status
    
    @status.setter                  # setter（等价 setStatus()）
    def status(self, value: str):
        if value not in ("pending", "shipped", "delivered"):
            raise ValueError(f"无效状态: {value}")
        self._status = value

# 使用（看起来像字段访问，实际走方法）
order = Order()
print(order.status)         # 调用 @property getter
order.status = "shipped"    # 调用 @status.setter
```

**本项目用法**：一般不需要 `@property`，直接用 `obj.attr` 访问即可。只有在需要**计算属性**或**设值校验**时才使用。

#### `__dunder__` 魔术方法

Python 用双下划线方法实现运算符重载和协议，类似于 Java 的 `toString()`、`equals()`、`hashCode()` 但覆盖面更广：

| Java | Python `__dunder__` | 用途 |
|------|---------------------|------|
| `toString()` | `__str__` | `str(obj)` / `print(obj)` 调用 |
| `equals()` | `__eq__` | `obj1 == obj2` 调用 |
| `hashCode()` | `__hash__` | `hash(obj)` / dict key 调用 |
| `compareTo()` | `__lt__`, `__gt__` | `obj1 < obj2` 调用 |
| 构造函数 | `__init__` | `ClassName()` 时调用 |
| `Iterable` 接口 | `__iter__`, `__next__` | `for x in obj` 调用 |
| `AutoCloseable` | `__enter__`, `__exit__` | `with obj:` 调用 |
| `size()` / `length()` | `__len__` | `len(obj)` 调用 |
| `get(index)` | `__getitem__` | `obj[key]` 调用 |
| `set(index, val)` | `__setitem__` | `obj[key] = val` 调用 |
| 无等价 | `__repr__` | 调试输出 `repr(obj)` 调用 |

**本项目最常见**：`__init__`（构造）、`__str__`/`__repr__`（输出）、`to_dict()`（本项目自定义，序列化为 JSON）。

#### Python 没有方法重载

```java
// Java: 方法重载（同名不同参数）
public void process(String input) { ... }
public void process(String input, int timeout) { ... }
public void process(String input, int timeout, Map<String, Object> options) { ... }
```

```python
# Python: 无方法重载，用默认参数 + **kwargs 代替
def process(
    input: str,
    timeout: int = 30,
    **options: Any,            # 接收任意额外参数
) -> None:
    ...

# 调用
process("hello")
process("hello", timeout=60)
process("hello", timeout=60, async_mode=True, retry=3)  # 额外参数进 options
```

#### `__pycache__` 和 `.pyc` 文件

```
# 项目中会出现这种目录，不需要手动处理
services/orchestrator-python/app/__pycache__/
    graph.cpython-312.pyc
    state.cpython-312.pyc
```

| Java | Python |
|------|--------|
| `.java` → 编译 → `.class` | `.py` → 自动缓存 → `.pyc` |
| 需要 `javac` 手动编译 | Python 运行时自动编译缓存 |
| 存放在 `target/` | 存放在 `__pycache__/` |
| `.gitignore` 排除 `target/` | `.gitignore` 排除 `__pycache__/` |

> **注意**：Python **不需要手动编译**。`.pyc` 是 Python 解释器自动生成的字节码缓存，加速下次导入。修改 `.py` 文件后缓存自动失效更新。可以安全删除 `__pycache__/`。

---

## 3. 核心语法与范式：Java → Python 思维切换

### 3.1 类型系统：静态约束 → 动态契约

| 维度 | Java | Python | 思维切换要点 |
|------|------|--------|-------------|
| 类型检查 | 编译期强制 | 运行时（可选类型提示） | Python 类型提示是**文档**，不是**约束** |
| 空安全 | `Optional<T>` + 显式判空 | `None` + 类型联合 `str \| None` | 无 `NullPointerException`，但需主动防御 |
| 泛型 | 类型擦除 + 运行时不可用 | 运行时可用（`list[dict]`） | Python 泛型更灵活，但无编译期校验 |
| 类型转换 | 显式强转 `(String) obj` | 鸭子类型 + `isinstance()` | **关注行为而非类型** |

```java
// Java: 编译器保证类型安全
public class OrderService {
    private final OrderRepository orderRepo;  // 编译期绑定
    
    public Optional<Order> findOrder(Long id) {
        return orderRepo.findById(id);  // 返回 Optional 强制判空
    }
}
```

```python
# Python: 类型提示 + 运行时校验（Pydantic 补位）
class OrderService:
    def __init__(self, order_repo: OrderRepository) -> None:
        self.order_repo = order_repo  # 仅类型提示，运行时不检查

    async def find_order(self, order_id: int) -> Order | None:
        return await self.order_repo.find_by_id(order_id)  # None 是合法返回值
```

**关键差异**：Python 的 `str | None` 等价于 Java 的 `Optional<String>`，但**不会在编译期强制你处理 None**。项目中通过 Pydantic V2 做运行时校验补位。

### 3.2 类与模块：class 中心 vs 函数优先

| 维度 | Java | Python |
|------|------|--------|
| 组织单元 | class 是唯一一等公民 | 函数、类、模块都是一等公民 |
| 访问控制 | `public/private/protected` | 命名约定 `_private` / `__mangled` |
| 继承 | 单继承 + interface | 多继承 + Mixin |
| 包管理 | package + import | 模块（.py 文件）+ 包（目录 + `__init__.py`） |

```java
// Java: 一切皆 class
public class OrderController {
    @Autowired
    private OrderService orderService;  // 依赖注入
    
    @GetMapping("/orders/{id}")
    public RestResult<OrderVO> getOrder(@PathVariable Long id) {
        return RestResult.success(orderService.getOrder(id));
    }
}
```

```python
# Python: 函数优先 + 依赖注入通过 FastAPI Depends
from fastapi import APIRouter, Depends

router = APIRouter()

@router.get("/orders/{order_id}")
async def get_order(
    order_id: int,
    service: OrderService = Depends(),  # FastAPI 依赖注入
) -> RestResult[OrderVO]:
    data = await service.get_order(order_id)
    return RestResult.success(data)
```

**思维切换**：Java 中过度使用 class 是惯性，Python 中优先考虑函数。Agent 的节点（node）本质上是**纯函数**：`state → dict`。

### 3.3 异常处理：受检异常 vs 极简异常

```java
// Java: 受检异常强制处理
public void process() throws BusinessException {
    if (invalid) {
        throw new BusinessException(ErrorCode.PARAM_ERROR);
    }
}

// 调用方必须 try-catch 或继续 throws
try {
    service.process();
} catch (BusinessException e) {
    log.error("业务异常", e);
    return RestResult.fail(e.getErrorCode());
}
```

```python
# Python: 无受检异常，统一异常体系（本项目实现）
from app.core.exceptions import InvalidRequestError, BasePlatformException

async def process():
    if invalid:
        raise InvalidRequestError("参数错误", details={"field": "name"})

# FastAPI 异常处理器统一捕获
@app.exception_handler(BasePlatformException)
async def handle_platform_exception(request, exc):
    return JSONResponse(status_code=400, content=exc.to_dict())
```

**映射关系**：

| Java | Python (本项目) |
|------|-----------------|
| `BusinessException` + `ErrorCode` 枚举 | `BasePlatformException` 子类 + `code` 属性 |
| `@RestControllerAdvice` 全局处理 | `@app.exception_handler()` 注册 |
| `RestResult.fail(errorCode)` | `exc.to_dict()` 自动格式化 |

### 3.4 异步编程：CompletableFuture → async/await

这是 Java 工程师最需要适应的范式差异。

```java
// Java: CompletableFuture 链式调用
CompletableFuture<Order> future = orderRepo.findById(id)
    .thenCompose(order -> riskService.check(order))
    .thenApply(result -> convertToVO(result))
    .exceptionally(ex -> { log.error("失败", ex); return null; });

// 或者用虚拟线程 (Java 21)
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    Order order = executor.submit(() -> orderRepo.findById(id)).get();
}
```

```python
# Python: async/await 原生协程
async def process_order(order_id: int) -> OrderVO:
    order = await order_repo.find_by_id(order_id)     # 自然顺序
    risk = await risk_service.check(order)            # 无回调嵌套
    return convert_to_vo(risk)

# 并发执行（等价于 CompletableFuture.allOf）
import asyncio
results = await asyncio.gather(
    order_repo.find_by_id(1),
    order_repo.find_by_id(2),
    risk_service.check_batch(orders),
)
```

**核心差异**：

| Java | Python | 说明 |
|------|--------|------|
| `CompletableFuture.supplyAsync()` | `asyncio.create_task()` | 创建并发任务 |
| `future.thenApply()` | `await coro` | Python 直接顺序写，async/await 消除回调 |
| `CompletableFuture.allOf()` | `asyncio.gather()` | 并发等待多个结果 |
| `ExecutorService` 线程池 | `asyncio.Semaphore` | 并发控制（本项目 Agent 中大量使用） |
| `synchronized` / `ReentrantLock` | `asyncio.Lock` | 协程级互斥（注意不是线程级） |
| `ThreadLocal` | `contextvars` | 协程级上下文传递 |

> **关键警告**：Python 的 `asyncio.Lock` 是**协程级锁**，不同于 Java 的线程级锁。在多线程环境中需用 `threading.Lock`。本项目熔断器改造时曾因此产生竞态问题（见 `resilience.py`）。

**async/await 铁律**（Java 工程师最常犯的错）：
```python
# ❌ 在 async 函数中调用阻塞 I/O（会阻塞整个事件循环！）
async def bad_example():
    time.sleep(5)                    # ❌ 阻塞！
    requests.get("http://api")       # ❌ 同步 HTTP 库！

# ✅ 必须使用 async 版本
async def good_example():
    await asyncio.sleep(5)           # ✅ 非阻塞等待
    async with httpx.AsyncClient() as client:
        resp = await client.get("http://api")  # ✅ 异步 HTTP

# ✅ 如果必须用阻塞库，放到线程池
import asyncio
result = await asyncio.to_thread(blocking_function, arg1, arg2)
```

### 3.5 数据类：Java Bean vs Python Data Model

```java
// Java: Lombok + JPA Entity
@Data
@Entity
@Table(name = "orders")
@EqualsAndHashCode(callSuper = true)
public class Order extends BaseEntity {
    @Column(name = "order_no", nullable = false, length = 64)
    private String orderNo;

    @Column(name = "status", length = 20)
    private String status;
}
```

```python
# Python 方案一：dataclass（简单场景）
from dataclasses import dataclass

@dataclass
class Order:
    order_no: str
    status: str = "pending"

# Python 方案二：Pydantic Model（API/校验场景，本项目主要使用）
from pydantic import BaseModel, Field

class OrderRequest(BaseModel):
    order_no: str = Field(..., min_length=1, max_length=64)
    status: str = Field(default="pending", pattern=r"^(pending|shipped|delivered)$")

# Python 方案三：TypedDict（状态机场景，本项目 AgentState 使用）
from typing import TypedDict, Annotated

class AgentState(TypedDict):
    messages: Annotated[list, add_messages]  # reducer 模式
    current_step: str
    tool_calls: list[dict]
```

**选择指南**：

| 场景 | Python 方案 | 等价 Java |
|------|------------|----------|
| API 请求/响应 | `pydantic.BaseModel` | `@Valid` + DTO |
| 内部数据传递 | `dataclass` | Lombok `@Data` |
| 状态机状态 | `TypedDict` | 无直接等价（自定义 Map） |
| 配置项 | `pydantic-settings` | `@ConfigurationProperties` |

### 3.6 字符串与字节

Python 3 严格区分 `str`（文本）和 `bytes`（二进制），Java 中 `String` 与 `byte[]` 的区别类似但更彻底：

```java
// Java: String ↔ byte[] 转换
String text = "你好";
byte[] data = text.getBytes(StandardCharsets.UTF_8);
String decoded = new String(data, StandardCharsets.UTF_8);
```

```python
# Python: str ↔ bytes 转换
text: str = "你好"
data: bytes = text.encode("utf-8")       # str → bytes
decoded: str = data.decode("utf-8")       # bytes → str

# ❌ 不能混用
# text + data     # TypeError: can only concatenate str (not "bytes") to str
# len(text) == 2  # 字符数
# len(data) == 6  # 字节数（UTF-8 中文 3 字节）
```

**本项目场景**：gRPC 通信时 JSON 序列化/反序列化：
```python
import orjson  # 比标准库 json 快 3-10 倍

# dict → bytes（gRPC 传输）
data: bytes = orjson.dumps({"order_id": "ORD-001"})

# bytes → dict
result: dict = orjson.loads(data)
```

---

## 4. Python Agent 开发关键生态

### 4.1 核心库矩阵

| 领域 | 库 | 本项目使用 | 等价 Java 生态 |
|------|-----|-----------|---------------|
| **Web 框架** | FastAPI | ✅ | Spring Boot |
| **状态机/Agent** | LangGraph | ✅ | 无直接等价 |
| **LLM 接入** | LangChain Core | ✅ | 无（自研 SDK） |
| **数据校验** | Pydantic V2 | ✅ | Hibernate Validator |
| **HTTP 客户端** | httpx | ✅ | OkHttp / RestClient |
| **gRPC** | grpcio | ✅ | gRPC Java |
| **异步** | asyncio | ✅ | CompletableFuture / Virtual Thread |
| **日志** | structlog | ✅ | SLF4J + Logback |
| **配置** | pydantic-settings | ✅ | @ConfigurationProperties |
| **重试** | tenacity | ✅ | Resilience4j |
| **ORM** | asyncpg (原生 SQL) | ✅ | Spring Data JPA |
| **缓存** | redis + cachetools | ✅ | Spring Data Redis |
| **可观测** | OpenTelemetry | ✅ | Micrometer + OTel |
| **序列化** | orjson | ✅ | Jackson |

### 4.2 FastAPI vs Spring Boot 速查

| 概念 | Spring Boot | FastAPI |
|------|------------|---------|
| 路由定义 | `@GetMapping("/api/orders")` | `@router.get("/api/orders")` |
| 请求参数 | `@PathVariable` / `@RequestParam` | 函数参数 + 类型提示 |
| 请求体 | `@RequestBody OrderRequest req` | `req: OrderRequest` (Pydantic 自动校验) |
| 依赖注入 | `@Autowired` + IoC 容器 | `Depends()` + 函数式注入 |
| 全局异常 | `@RestControllerAdvice` | `@app.exception_handler()` |
| 拦截器 | `HandlerInterceptor` | `@app.middleware("http")` |
| 参数校验 | `@Valid` + JSR 303 | Pydantic 内置校验 + `Field()` |
| API 文档 | Swagger 自动生成 | OpenAPI 自动生成（更优） |
| 应用生命周期 | `@PostConstruct` / `@PreDestroy` | `lifespan` 上下文管理器 |
| 启动入口 | `SpringApplication.run(App.class)` | `uvicorn app.main:app` |

**FastAPI 应用生命周期**（本项目实现）：
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ─── 启动（等价 @PostConstruct） ───
    global redis_client
    redis_client = Redis.from_url(config.redis_url)
    await grpc_channel.connect()
    
    yield  # 应用运行中
    
    # ─── 关闭（等价 @PreDestroy） ───
    await redis_client.close()
    await grpc_channel.close()

app = FastAPI(lifespan=lifespan)
```

### 4.3 LangGraph：Agent 的状态机框架

LangGraph 是本项目的核心框架，理解其与 Java 状态机的对应关系至关重要。

**LangGraph ≈ Spring StateMachine + Redux**

| LangGraph | Java 等价 | 说明 |
|-----------|----------|------|
| `StateGraph(AgentState)` | `StateMachine<OrderState, OrderEvent>` | 状态机定义 |
| `graph.add_node("name", func)` | `builder.source("S1").target("S2").event("E1")` | 添加节点 |
| `graph.add_edge("A", "B")` | 状态转移规则 | 无条件边 |
| `graph.add_conditional_edges()` | `guard(condition)` | 条件路由 |
| `graph.compile()` | `builder.build()` | 构建可执行状态机 |
| `graph.invoke(state)` | `stateMachine.sendEvent(event)` | 执行一步 |
| `graph.stream(state)` | 无直接等价 | 流式输出 |
| `MemorySaver` / Checkpointer | 持久化 StateMachine | 状态持久化 |
| `interrupt_before` | 无直接等价 | 暂停等待外部输入 |

---

## 5. Agent 架构设计原理与 Python 实现

### 5.1 Agent 本质：推理-行动循环

Agent 是一个**状态机**，核心循环为：

```
用户输入 → 推理(thinking) → 决策 → 执行(tool_call) → 观察结果 → 继续推理 → 最终回答
```

这不同于传统 Java 应用的**请求-响应**模式。Java 服务是确定性的流程编排，Agent 是**非确定性的推理循环**——LLM 的输出决定下一步走向。

**与 Java 服务对比**：

```
Java 服务:  Request → Controller → Service → Repository → Response  （确定性流程）
Agent:      Request → Thinking → [LLM决定] → Tool/Answer → Thinking → ...  （推理循环）
```

### 5.2 状态管理：不可变状态 + Reducer 模式

本项目采用 LangGraph 的 **TypedDict + Annotated Reducer** 模式管理状态，类似 React/Redux 的设计思想。

```python
# 本项目实际状态定义
from typing import Annotated, TypedDict
from langgraph.graph.message import add_messages

class AgentState(TypedDict):
    # 消息累积：add_messages reducer 自动追加而非覆盖
    messages: Annotated[list, add_messages]
    
    # 执行控制
    step_count: int
    max_steps: int
    current_step: str
    
    # 工具调用
    tool_calls: list[dict]
    tool_results: list[dict]
    
    # 风控
    risk_level: str
    approval_id: str | None
    approval_status: str | None
    
    # 错误
    error: str | None
    error_code: str | None
    consecutive_errors: int
```

**与 Java 状态管理对比**：

| 维度 | Java 传统 | LangGraph State |
|------|----------|-----------------|
| 状态载体 | 对象（可变） | TypedDict（逻辑不可变） |
| 状态更新 | `state.setStatus("running")` | `return {"current_step": "tool_call"}` |
| 状态合并 | 手动赋值 | 自动合并（浅合并） |
| 消息累积 | `list.add(msg)` | `add_messages` reducer 自动追加 |
| 状态回滚 | 需手动实现 | Checkpoint 自动支持 |
| 并发安全 | `synchronized` / 锁 | 协程模型天然安全（单线程事件循环） |

**节点返回状态更新的核心机制**：

```python
# 节点只返回需要更新的字段（类似 Redux reducer）
async def thinking_node(state: AgentState) -> dict:
    # 读取当前状态
    step_count = state["step_count"]
    
    # 执行推理逻辑
    decision = await llm_infer(state["messages"])
    
    # 只返回更新的部分，LangGraph 自动合并
    return {
        "step_count": step_count + 1,
        "current_step": decision.next_step,
        "tool_calls": decision.tool_calls,
    }
    # LangGraph 合并：new_state = {**old_state, **returned_updates}
```

### 5.3 工具调用：从本地方法到外部 gRPC

Java 中"工具"就是普通方法调用，Agent 中"工具"是与 LLM 交互的特殊抽象。

**Java 思维**：工具 = 本地方法
```java
@Autowired
private OrderService orderService;

public OrderVO queryOrder(String orderId) {
    return orderService.getById(orderId);  // 直接调用
}
```

**Agent 思维**：工具 = LLM 可调用的外部能力
```python
from app.tools.clients.tool_bus_client import ToolBusClient

client = ToolBusClient()
result = await client.execute_tool(
    tool_name="query_order_status",          # 工具名（LLM 选择）
    arguments={"order_id": "ORD-12345"},     # LLM 生成的参数
    context={
        "request_id": "req_xyz",             # 链路追踪
        "tenant_id": "tenant_001",            # 租户隔离
        "user_id": "user_001",                # 权限校验
    },
)
```

**差异本质**：Agent 的工具调用由 LLM 决定**何时调用**和**调用什么**，而非程序员硬编码。

**工具调用流程**：
```
1. thinking 节点：LLM 输出 tool_calls（决定调用什么工具、什么参数）
2. risk_check 节点：评估风险等级
3. tool_call 节点：通过 ToolBus gRPC 实际执行
4. 结果写回 state.tool_results
5. 回到 thinking 节点：LLM 根据结果继续推理
```

**工具定义规范**（JSON Schema 描述，供 LLM 理解）：
```json
{
    "name": "query_order_status",
    "description": "查询订单状态",
    "input_schema": {
        "type": "object",
        "properties": {
            "order_id": {"type": "string", "description": "订单号"}
        },
        "required": ["order_id"]
    },
    "risk_level": "low",
    "requires_approval": false
}
```

### 5.4 LLM 交互：从数据库查询到模型推理

传统 Java 应用的核心 I/O 是数据库，Agent 的核心 I/O 是 LLM 推理。

```python
# Python: LLM 是核心 I/O
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(
    model="qwen-max",
    base_url=config.model_base_url,
    api_key=config.model_api_key,
    temperature=0.1,
    max_tokens=4096,
)

# 同步调用
response = await llm.ainvoke(messages)

# 流式调用（SSE 推送）
async for chunk in llm.astream(messages):
    yield chunk.content
```

**LLM 交互的特殊考量**（Java 工程师容易忽视）：

| 维度 | 数据库 I/O | LLM I/O |
|------|-----------|---------|
| 延迟 | 毫秒级 | 秒级（5-30s） |
| 确定性 | SQL 结果确定 | 相同输入可能不同输出 |
| Token 限制 | 无 | 上下文窗口（128K tokens） |
| 超时 | 简单设置 | 需要熔断 + 降级 |
| 成本 | 固定 | 按请求计费 |
| 安全性 | SQL 注入 | Prompt 注入 |

本项目通过以下机制应对：
- `context_manager.py`：滑动窗口截断，防止 token 超限
- `resilience.py`：熔断器 + 降级，防止模型不可用时雪崩
- `prompt_guard.py`：Prompt 注入防护
- `token_counter.py`：精确 token 计数

### 5.5 审批与中断：interrupt 机制

Agent 中高风险操作需要人工审批，LangGraph 的 `interrupt_before` 机制允许状态机暂停，等待外部输入后恢复。

```python
# 编译图时指定中断节点
graph = builder.compile(
    checkpointer=PostgresSaver(db),      # 状态持久化
    interrupt_before=["approval_wait"],  # 在审批节点前暂停
)

# 执行到 approval_wait 时暂停，返回当前状态
result = await graph.ainvoke(initial_state)

# ... 用户审批通过 ...

# 从 checkpoint 恢复执行
result = await graph.ainvoke(
    {"approval_status": "approved"},
    config={"configurable": {"thread_id": session_id}},
)
```

**Java 等价**：类似于 Java 中工作流引擎（如 Camunda）的 **User Task** 节点。

### 5.6 并发控制：协程级信号量

```python
# 本项目并发控制实现
_model_semaphore: asyncio.Semaphore | None = None
_tool_semaphore: asyncio.Semaphore | None = None

def get_model_semaphore() -> asyncio.Semaphore:
    """获取模型调用并发信号量"""
    global _model_semaphore
    if _model_semaphore is None:
        _model_semaphore = asyncio.Semaphore(MAX_CONCURRENT_MODEL_CALLS)
    return _model_semaphore

# 在节点中使用
async def thinking_node(state: AgentState) -> dict:
    sem = get_model_semaphore()
    async with sem:  # 等价 Java 的 Semaphore.acquire()/release()
        response = await llm.ainvoke(messages)
```

---

## 6. 实战编码模式对比

### 6.1 异常体系

```java
// Java: 枚举 + 自定义异常
public enum BusinessErrorCode implements ErrorCode {
    PARAM_ERROR(2500, "请求参数错误"),
    USER_NOT_FOUND(2501, "用户不存在");
}

// 使用
BusinessValidators.isTrueThrow(condition, BusinessErrorCode.PARAM_ERROR);
```

```python
# Python: 异常类即错误码（本项目实现）
class BasePlatformException(Exception):
    def __init__(self, message: str, code: str = "ERR_UNKNOWN",
                 user_message: str | None = None, details: dict | None = None):
        self.message = message       # 技术信息（日志）
        self.code = code            # 错误码（前端）
        self.user_message = user_message or message  # 用户友好信息
        self.details = details or {}

# 使用
raise InvalidRequestError("参数错误", details={"field": "order_id"})
```

### 6.2 依赖注入

```java
// Java: Spring IoC 容器管理
@RestController
public class OrderController {
    @Autowired
    private OrderService orderService;
}
```

```python
# Python 方案一：FastAPI Depends（推荐）
from fastapi import Depends

@router.post("/chat")
async def chat(
    request: ChatRequest,
    service: AgentService = Depends(),
    user: User = Depends(get_current_user),
) -> RestResult[ChatResponse]:
    return await service.chat(request, user)

# Python 方案二：模块级单例（本项目 gRPC 客户端）
_tool_bus_client: ToolBusClient | None = None

def get_tool_bus_client() -> ToolBusClient:
    global _tool_bus_client
    if _tool_bus_client is None:
        _tool_bus_client = ToolBusClient(config.tool_bus_url)
    return _tool_bus_client
```

### 6.3 配置管理

```java
// Java: @ConfigurationProperties
@ConfigurationProperties(prefix = "agent")
@Data
public class AgentProperties {
    private int maxSteps = 10;
    private int modelCallTimeoutS = 30;
}
```

```python
# Python: pydantic-settings（本项目实现）
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    max_agent_steps: int = 10
    model_call_timeout_s: int = 30
    tool_call_timeout_s: int = 15
    max_user_input_tokens: int = 8000
    
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",        # 环境变量前缀
        env_file=".env",            # 支持 .env 文件
        env_file_encoding="utf-8",
    )

config = Settings()  # 自动读取环境变量，自动类型转换和校验
```

### 6.4 日志记录

```java
// Java: SLF4J + Lombok
@Slf4j
@Service
public class OrderService {
    public void process(Order order) {
        log.info("处理订单: orderId={}", order.getId());
    }
}
```

```python
# Python: structlog 结构化日志（本项目实现）
import structlog

logger = structlog.get_logger()

async def thinking_node(state: AgentState) -> dict:
    logger.info("node_started", node="thinking", request_id=state["request_id"])
    # 输出: {"event": "node_started", "node": "thinking", "request_id": "req_abc"}
```

### 6.5 完整流程对比：Java CRUD vs Python Agent

**Java: 确定性 CRUD 流程**
```java
@RestController @Slf4j
public class OrderController {
    @Autowired private OrderService orderService;
    
    @GetMapping("/orders/{id}")
    public RestResult<OrderVO> getOrder(@PathVariable Long id) {
        return RestResult.success(orderService.getById(id));
    }
}
```

**Python: 非确定性 Agent 推理流程**
```python
# 1. 状态定义
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    current_step: str
    tool_calls: list[dict]

# 2. 推理节点（等价 Service，但由 LLM 驱动）
async def thinking_node(state: AgentState) -> dict:
    response = await llm.ainvoke(state["messages"])
    if response.tool_calls:
        return {"current_step": "tool_call", "tool_calls": response.tool_calls}
    return {"current_step": "final_answer", "output": response.content}

# 3. 工具调用节点
async def tool_call_node(state: AgentState) -> dict:
    results = []
    for call in state["tool_calls"]:
        result = await tool_bus.execute_tool(
            tool_name=call["name"],
            arguments=call["arguments"],
            context={"tenant_id": state["tenant_id"]},
        )
        results.append(result)
    return {"tool_results": results, "current_step": "thinking"}

# 4. 图构建（等价 Java 的流程编排）
graph = StateGraph(AgentState)
graph.add_node("thinking", thinking_node)
graph.add_node("tool_call", tool_call_node)
graph.add_conditional_edges("thinking", route_after_thinking, {
    "tool_call": "tool_call",
    "final_answer": "final_answer",
})
graph.add_edge("tool_call", "thinking")
```

### 6.6 测试

```java
// Java: Spring Boot Test + Mock
@SpringBootTest
class OrderServiceTest {
    @MockBean private OrderRepository orderRepo;
    
    @Test
    void shouldReturnOrder() {
        when(orderRepo.findById(1L)).thenReturn(Optional.of(new Order()));
        OrderVO result = orderService.getById(1L);
        assertThat(result.getOrderNo()).isEqualTo("ORD-001");
    }
}
```

```python
# Python: pytest + asyncio（本项目风格）
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_thinking_node_should_request_tool_call():
    state = create_initial_state(
        input="查询订单 ORD-12345",
        session_id="test", tenant_id="t1", user_id="u1", request_id="r1",
    )
    
    with patch("app.graph.nodes.thinking.llm") as mock_llm:
        mock_llm.ainvoke = AsyncMock(return_value=MockResponse(
            tool_calls=[{"name": "query_order_status", "arguments": {"order_id": "ORD-12345"}}],
        ))
        result = await thinking_node(state)
    
    assert result["current_step"] == "tool_call"
    assert len(result["tool_calls"]) == 1

# pytest 常用断言
assert result is not None            # assertNotNull
assert result["status"] == "ok"      # assertEquals
assert "error" not in result         # assertFalse(result.containsKey("error"))
assert len(items) > 0                # assertTrue(items.size() > 0)
with pytest.raises(InvalidRequestError):  # @Test(expected = ...)
    validate_input("")
```

---

## 7. Python 常见陷阱（Java 工程师必读）

### 7.1 可变默认参数

```python
# ❌ 经典陷阱：默认参数在函数定义时求值，而非调用时
def append_item(item, items=[]):   # items 是同一个对象！
    items.append(item)
    return items

print(append_item("a"))  # ["a"]
print(append_item("b"))  # ["a", "b"]  ← 不是 ["b"]！

# ✅ 正确写法
def append_item(item, items=None):
    if items is None:
        items = []
    items.append(item)
    return items
```

### 7.2 浅拷贝与嵌套结构

```python
# Python 赋值是引用，不是拷贝（类似 Java 对象赋值）
original = {"orders": [1, 2, 3]}
copy = original              # ❌ 这不是拷贝！指向同一个对象
copy["orders"].append(4)
print(original["orders"])    # [1, 2, 3, 4]  ← original 也被修改了！

# ✅ 浅拷贝
copy = original.copy()       # 等价 new HashMap<>(original)
copy = {**original}          # 解包方式

# ✅ 深拷贝（嵌套结构）
import copy
copy = copy.deepcopy(original)  # 等价 Java 序列化反序列化
```

### 7.3 `is` vs `==`

```python
# == 比较值（等价 Java 的 equals()）
# is 比较身份/内存地址（等价 Java 的 ==）

a = [1, 2, 3]
b = [1, 2, 3]
assert a == b      # True  - 值相等
assert a is b      # False - 不是同一个对象

# 唯一例外：None 比较用 is
if value is None:   # ✅ Python 惯用
    ...
if value == None:   # ❌ 不推荐
    ...
```

### 7.4 闭包延迟绑定

```python
# ❌ 闭包捕获的是变量引用，不是值
funcs = []
for i in range(5):
    funcs.append(lambda: i)          # 所有 lambda 捕获的是同一个 i

print([f() for f in funcs])  # [4, 4, 4, 4, 4]  ← 不是 [0, 1, 2, 3, 4]！

# ✅ 用默认参数绑定当前值
funcs = []
for i in range(5):
    funcs.append(lambda i=i: i)     # 默认参数在定义时求值

print([f() for f in funcs])  # [0, 1, 2, 3, 4]
```

### 7.5 字典遍历中修改

```python
# ❌ 遍历时不能修改字典大小
for key in d:
    if should_remove(key):
        del d[key]          # RuntimeError: dictionary changed size

# ✅ 收集 key 后删除
for key in list(d.keys()):  # list() 创建副本
    if should_remove(key):
        del d[key]

# ✅ 字典推导
d = {k: v for k, v in d.items() if not should_remove(k)}
```

### 7.6 `__str__` vs `__repr__`

```java
// Java: toString() 用于所有场景
@Override
public String toString() { return "Order{id=" + id + "}"; }
```

```python
# Python: 两个方法，用途不同
class Order:
    def __str__(self):           # 面向用户（等价 Java toString）
        return f"订单 #{self.id}"
    
    def __repr__(self):          # 面向开发者（调试用）
        return f"Order(id={self.id}, no={self.order_no!r})"

# 交互示例
>>> str(order)     # "订单 #123"        （print(order) 调用）
>>> repr(order)    # "Order(id=123, no='ORD-001')"  （直接输入变量名调用）
```

### 7.7 import 机制

```python
# Python import 不同于 Java import
# Java: import 是编译期类型引用
# Python: import 是运行时代码执行

# 绝对导入（推荐，本项目使用）
from app.core.config import config        # 明确路径
from app.graph.state import AgentState    # 从项目根开始

# 相对导入（仅包内部使用）
from .state import AgentState             # 同目录
from ..core.config import config          # 上级目录

# ❌ 避免
from app.core import *                    # 污染命名空间（等价 Java 的 import xxx.*）
```

**循环导入**是 Python 特有问题（Java 无此问题，因为编译期处理）：
```python
# ❌ 循环导入
# a.py
from b import something_b  # b.py 还没加载完
# b.py
from a import something_a  # a.py 还没加载完

# ✅ 解决方案
# 1. 把共享代码提取到 c.py
# 2. 在函数内部导入（延迟导入）
def process():
    from b import something_b  # 运行时才导入
```

---

## 8. 读懂 Python 错误追踪

Python 报错方式与 Java 截然不同，学会读 Traceback 是调试第一步。

### 8.1 错误追踪格式

```python
# Python Traceback（从下往上看！最后一行是根因）
Traceback (most recent call last):                          ← 最先执行的
  File "app/api/v1/chat.py", line 45, in chat_endpoint     ← API 入口
    result = await agent_service.chat(request)
  File "app/core/agent_service.py", line 78, in chat       ← Service 层
    result = await graph.ainvoke(state)
  File "app/graph/builder.py", line 112, in thinking_node   ← 节点
    response = await llm.ainvoke(messages)
  File "langchain_openai/chat_models/base.py", line 234     ← 第三方库
    raise ValueError("Invalid API key")
ValueError: Invalid API key                                 ← 根因！
```

```java
// Java Stack Trace（从上往上看！最上面是异常抛出点）
java.lang.IllegalArgumentException: Invalid API key        ← 根因！
    at com.example.AgentService.chat(AgentService.java:78)  ← 抛出点
    at com.example.ChatController.chat(ChatController.java:45)
    at sun.reflect.NativeMethodAccessorImpl.invoke0(Native)
    ...
```

**关键差异**：Python Traceback **从下往上看**（最后一行是错误），Java Stack Trace **从上往上看**（第一行是错误）。

### 8.2 常见错误类型映射

| Python 错误 | Java 等价 | 含义 |
|-------------|----------|------|
| `TypeError` | `ClassCastException` | 类型错误 |
| `ValueError` | `IllegalArgumentException` | 值不合法 |
| `KeyError` | `NoSuchElementException` | 字典 key 不存在 |
| `AttributeError` | `NullPointerException` / `NoSuchMethodError` | 对象无此属性/方法 |
| `ImportError` | `ClassNotFoundException` | 模块导入失败 |
| `FileNotFoundError` | `FileNotFoundException` | 文件不存在 |
| `IndexError` | `IndexOutOfBoundsException` | 索引越界 |

### 8.3 常见报错与修复

```python
# 1. AttributeError: 'NoneType' object has no attribute 'xxx'
#    等价 Java: NullPointerException
result = await repo.find_by_id(999)   # 返回 None
result["name"]                        # ❌ None 没有 [] 操作
# ✅ 修复：判空
if result is not None:
    name = result["name"]
# ✅ 或用 get()
name = result.get("name", "默认值") if result else "默认值"

# 2. KeyError: 'order_id'
#    等价 Java: Map 中 key 不存在
data = {"name": "test"}
order_id = data["order_id"]           # ❌ key 不存在
# ✅ 修复：用 get()
order_id = data.get("order_id")        # 返回 None
order_id = data.get("order_id", "")    # 返回默认值

# 3. TypeError: 'coroutine' object is not subscriptable
#    等价 Java: 忘记 CompletableFuture.get()
result = async_function()              # ❌ 忘记 await！
result = await async_function()        # ✅ 必须加 await

# 4. ImportError: cannot import name 'xxx' from 'module'
#    等价 Java: ClassNotFoundException
#    原因：模块不存在 / 路径错误 / 未安装依赖
#    修复：uv add xxx / 检查 import 路径
```

---

## 9. 开发调试实操

### 9.1 运行与调试

```bash
# 启动开发服务器（热重载）
cd services/orchestrator-python
uv run uvicorn app.main:app --reload --port 8000

# 运行单个 Python 文件
uv run python scripts/verify_production_ready.py

# 运行测试
uv run pytest tests/ -v                    # 全部
uv run pytest tests/unit/ -v               # 单元测试
uv run pytest tests/unit/test_xxx.py -v    # 单文件
uv run pytest tests/unit/test_xxx.py::test_func -v  # 单函数
uv run pytest tests/ -v --cov=app          # 带覆盖率

# 类型检查
uv run mypy app/graph/state.py             # 单文件
uv run mypy app/                           # 全部

# 代码格式化 + Lint
uv run ruff format app/                    # 格式化
uv run ruff check app/                     # Lint
uv run ruff check app/ --fix               # 自动修复
```

### 9.2 IDE 调试（VS Code）

```json
// .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "FastAPI Debug",
            "type": "debugpy",
            "request": "launch",
            "module": "uvicorn",
            "args": ["app.main:app", "--reload", "--port", "8000"],
            "cwd": "${workspaceFolder}/services/orchestrator-python"
        }
    ]
}
```

### 9.3 交互式调试

```python
# 方法一：断点（IDE 中使用）
breakpoint()  # 等价 Java 的 int a = 1; // 在这里打断点

# 方法二：debugpy 远程调试
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()  # 等 VS Code 连接后继续

# 方法三：快速查看变量
print(f"当前状态: {state}")  # 简单粗暴但有效
logger.debug("state_dump", state=dict(state))  # 结构化输出
```

### 9.4 常用命令速查表

| 操作 | 命令 |
|------|------|
| 安装依赖 | `uv sync` |
| 启动服务 | `uv run uvicorn app.main:app --reload` |
| 运行测试 | `uv run pytest tests/ -v` |
| 添加依赖 | `uv add httpx` |
| 格式化 | `uv run ruff format app/` |
| Lint | `uv run ruff check app/` |
| 类型检查 | `uv run mypy app/` |
| 查看 Python 版本 | `uv run python --version` |
| 进入 Python REPL | `uv run python` |

---

## 10. 思维陷阱与最佳实践

### 10.1 Java 工程师常见思维陷阱

| 陷阱 | 表现 | 正确做法 |
|------|------|---------|
| 过度使用 class | 为简单函数创建不必要的类 | Python 优先使用函数和模块 |
| 滥用继承 | 用继承复用代码 | 优先组合 + Mixin |
| 追求编译期安全 | 在 Python 中模拟 Java 类型系统 | 类型提示 + Pydantic 运行时校验 |
| 忽视协程模型 | 在 async 函数中用阻塞 I/O | 全链路 async，阻塞操作用 `asyncio.to_thread` |
| 过度设计模式 | 套用 Java 23 种设计模式 | Python 崇尚简单（`import this`） |
| 忽视 GIL | 以为多线程能加速 CPU 密集任务 | CPU 密集用多进程，I/O 密集用协程 |
| 类比 JPA | 在 Python 中找 Hibernate | Python 生态更倾向原生 SQL 或轻量 ORM |
| 忽视动态性 | 改了接口以为所有调用方会报错 | Python 无编译期检查，靠测试 + 类型提示 |
| 万能 getter/setter | 写 `getX()` / `setX()` | Python 用 `obj.attr` 直接访问，需要时用 `@property` |
| 到处 try-catch | 每个 await 都包 try | 统一在异常处理器层处理，业务层只捕获需要特殊处理的 |

### 10.2 GIL：Java 工程师必须理解的核心差异

GIL（Global Interpreter Lock）是 Python 与 Java 并发模型**最根本的区别**，不理解它会导致所有并发设计决策错误。

**GIL 是什么**：CPython（官方 Python 实现）中一把全局互斥锁，**同一时刻只允许一个线程执行 Python 字节码**。

**与 Java 并发模型对比**：

```
Java:  线程1 ─── 执行 ───→
      线程2 ─── 执行 ───→    真正并行（多核）
      线程3 ─── 执行 ───→

Python (GIL):
      线程1 ──▓▓──▓▓──→    交替执行，同时刻只有一个线程在跑
      线程2 ──▓▓──▓▓──→    （▓▓ = 持有 GIL 执行中，── = 等待 GIL）
      线程3 ──▓▓──▓▓──→
```

**对实际开发的影响**：

| 场景 | Java 多线程 | Python 多线程 | Python 正确方案 |
|------|------------|--------------|----------------|
| CPU 密集（计算） | ✅ 利用多核 | ❌ GIL 限制，比单线程还慢 | **多进程** `multiprocessing` |
| I/O 密集（网络/磁盘） | ✅ 高效 | ⚠️ 可用，但 asyncio 更高效 | **协程** `asyncio` |
| 混合场景 | 线程池 | ⚠️ 受限 | **协程 + 进程池** |

**本项目方案**：完全使用 `asyncio` 协程，不使用多线程。因为 Agent 的 I/O 特征（LLM 调用、gRPC、Redis）天然适合协程。

```python
# ❌ Java 思维：用多线程加速
import threading
def process_tasks(tasks):
    threads = [threading.Thread(target=process, args=(t,)) for t in tasks]
    for t in threads: t.start()
    for t in threads: t.join()
    # 结果：因 GIL，没有加速，反而有线程切换开销

# ✅ Python 思维：I/O 密集用协程
import asyncio
async def process_tasks(tasks):
    results = await asyncio.gather(*[process(t) for t in tasks])
    # 结果：单线程事件循环，I/O 等待时自动切换，效率极高

# ✅ Python 思维：CPU 密集用进程池
import asyncio
async def compute_heavy(tasks):
    loop = asyncio.get_event_loop()
    results = await asyncio.gather(*[
        loop.run_in_executor(None, cpu_intensive_func, t)  # 在进程池中执行
        for t in tasks
    ])
```

### 10.3 本项目 Python 编码规范速查

```python
# ✅ 推荐
from typing import Annotated

async def thinking_node(state: AgentState) -> dict:  # 类型提示
    """节点说明（docstring 必须）"""
    logger.info("node_started", node="thinking")      # structlog
    return {"current_step": "tool_call"}               # 返回部分更新

# ❌ 避免
class ThinkingNodeHandler:                              # 过度封装
    def process(self, state):                           # 缺类型提示
        print("started")                                # 用 print 不用 logger
        state["current_step"] = "tool_call"             # 直接修改状态
        return state                                    # 返回完整状态
```

---

## 11. 延伸阅读

| 资源 | 说明 |
|------|------|
| [Agent 开发指南](./agent-dev-guide.md) | 本项目 Agent 开发详细指南 |
| [工程规范](./01-engineering-standards.md) | 代码结构、日志规范 |
| [通信契约](./02-communication-contracts.md) | API、错误码、gRPC 契约 |
| [安全规范](./03-security-specification.md) | 风控、审计、权限 |
| [LangGraph 文档](https://langchain-ai.github.io/langgraph/) | 状态机框架官方文档 |
| [FastAPI 文档](https://fastapi.tiangolo.com/) | Web 框架官方文档 |
| [Pydantic V2 文档](https://docs.pydantic.dev/) | 数据校验框架 |
| [Python asyncio 文档](https://docs.python.org/3/library/asyncio.html) | 异步编程参考 |
| [uv 文档](https://docs.astral.sh/uv/) | Python 包管理工具 |
| [ruff 文档](https://docs.astral.sh/ruff/) | Python Linter + Formatter |
