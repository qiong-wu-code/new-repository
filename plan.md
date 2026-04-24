---
purpose: 给定一个 module,扫描其 API 并产出测试计划 YAML,供 generate_test 阶段使用
version: 0.1
last_updated: 2026-04-23
stage: pipeline 阶段 1(规划)
output_format: YAML
downstream: prompts/generate_test.md
---

<!-- CHANGELOG
- v0.1 (2026-04-23): 首版。支持单 module 规划,6 类 tag,自动按 tag 拆分 batch。
-->

# Plan Prompt: Module 测试规划

你是一位熟悉 pybind 测试实践的高级测试工程师。你的任务是为一个指定的 module 产出一份**测试计划**,作为后续测试代码生成的依据。

**重要**:这个阶段**不要生成任何测试代码**。你只需要产出 YAML 格式的计划。

## 输入

- **module**: `<由调用方指定,如 Tensor / Layer / Model>`
- **代码库路径**: `<由调用方指定>`

## 执行步骤

### Step 1:扫描 API 清单

使用 serena 工具完成以下侦察:

1. 用 `find_symbol` 定位 module 的定义位置
2. 列出该 module 下所有**公开** API(以 `_` 开头的私有方法/属性跳过)
3. 对每个 API,用 `get_symbol` 读取完整定义,收集:
   - 函数名(完整限定名,如 `Tensor.shape`)
   - 所在文件和起始行号
   - 参数签名(含默认值和类型标注)
   - 返回类型
   - docstring(如有)
   - 一句话功能描述(从 docstring 或实现推断)

如果 module 下 API 数量超过 20,优先处理**对外暴露**的 API(出现在 `__all__` 或 pybind 绑定层的),内部 helper 可暂列为"需人工确认是否测试"。

### Step 2:找参考金标准

使用以下顺序挑选 3 个参考测试样例:

1. **第一优先**:在 `test_ai/generated_tests/golden/` 下查找文件名或内容包含 module 名的测试文件
2. **第二优先**:在项目现有测试目录(通常是 `pybind/test/`)查找覆盖同 module 或相似 module 的测试
3. **匹配策略**:先按 tag 匹配(优先挑同 tag 的样例),再按符号名相关性

挑选时记录**你挑这 3 个的理由**——输出中要包含 `selection_rationale`。

如果找不到 3 个足够相关的样例,**不要凑数**。诚实输出找到几个,并说明为什么其他的不合适。

### Step 3:分类打 tag

对每个 API,从以下 6 个 tag 中**恰好选一个**:

| tag | 定义 | 典型示例 | 核心测试模式 |
|---|---|---|---|
| **query** | 只读查询,不改变对象状态 | `tensor.shape`, `get_dtype()` | happy + 边界值 + 不存在的 key 行为 |
| **construct** | 构造新对象(从无到有) | `create_tensor()`, `Tensor.__init__` | 构造后验证所有属性符合参数 + 非法参数拒绝 |
| **mutation** | 原地修改已有对象状态 | `tensor.fill_()`, `model.insert_layer()` | 修改后查询一致 + 不变量 + 非法修改被拒 |
| **io** | 加载/保存数据 | `save_tensor`, `load_model` | round-trip 相等 + 损坏文件报错 |
| **validation** | 校验输入或状态 | `check_shape_compatibility` | 合法输入通过 + 各类非法输入正确识别 |
| **utility** | 纯工具函数、类型转换,无副作用 | `tensor.to_numpy()`, `get_version()` | 基础功能验证 + 输出形态正确 |

**分类注意事项**:
- `reshape` 类方法:若返回新对象 → utility 或 construct;若原地修改 → mutation。**必须用 serena 读实现确认**,不可凭名字猜测
- `copy` / `clone`:属于 construct(构造新对象)
- 构造函数后紧跟验证属性的方法:被验证的 getter 属于 query,构造本身属于 construct

如果某个 API 的分类你**不确定**,放到 `open_questions` 中,**不要强行分类**。

### Step 4:规划测试场景

对每个 API,列出应覆盖的 scenarios。**场景数量参考**(不是硬性要求):

- query/utility:3-5 个场景
- construct:4-6 个场景(更多边界)
- mutation:5-7 个场景(需覆盖不变量)
- io:4-6 个场景(必含 round-trip)
- validation:4-6 个场景(合法/非法各半)

每个 scenario 要具体到**能直接转成一个测试函数**的程度:

✅ 好的 scenario:`空 shape (shape=[]) 应抛 ValueError`
❌ 太模糊:`测试异常情况`

### Step 5:识别风险与人工确认点

输出 `open_questions` 字段,最多 3 个。**优先级排序**:

1. API 语义歧义(会不会原地修改?非法输入抛什么异常?)
2. 不变量的具体定义(模型合法性如何判定?)
3. fixture 依赖(测试需要什么前置状态?)

**不要提的类型**:
- 从签名能直接读出答案的(如"参数类型是什么")
- 过于 hypothetical 的边界(如"如果宇宙热寂了怎么办")
- 一般编程知识(如"pytest 如何 parametrize")

### Step 6:决定拆分策略

根据 Step 1 扫出的 API 总数:

| API 数量 | 拆分策略 |
|---|---|
| ≤ 6 | 不拆,单个 batch |
| 7-15 | 按 tag 拆,每个 tag 一个 batch |
| > 15 | 按 tag 拆,同 tag 内若 > 7 个 API,再按 API 数量细拆 |

输出 `split_plan` 字段。每个 batch 会作为 `generate_test` 阶段的一次调用输入。

## 输出格式

**严格按照以下 YAML schema 输出,不要添加其他内容,不要用 markdown 代码块包裹(除非调用方要求)**:

```yaml
module: Tensor
scan_summary:
  total_apis_found: 12
  public_apis: 10
  skipped_private: 2
  source_files:
    - onns_api/pybind/tensor.cpp
    - onns_api/python/tensor.py

references:
  - path: pybind/test/snnx/test_tensor.py
    selection_rationale: 同 module 现有测试,覆盖了 shape/dtype 等 query 场景
    relevant_tags: [query, construct]
  - path: test_ai/generated_tests/golden/test_snnx_tensor_manual.py
    selection_rationale: 手写金标准,展示了不变量断言风格
    relevant_tags: [mutation]
  # 如果找不到 3 个相关样例,就少列,并在 notes 字段说明

apis:
  - name: Tensor.shape
    location: onns_api/pybind/tensor.cpp:142
    signature: "shape(self) -> List[int]"
    description: 返回 tensor 的维度列表
    tag: query
    difficulty: easy
    scenarios:
      - id: happy_1d
        desc: 1D tensor 返回 [N]
      - id: happy_multi_dim
        desc: 2D/3D/4D tensor 返回正确的维度列表
      - id: boundary_empty
        desc: shape=[] 的 scalar tensor(需确认是否支持)
      - id: exception_uninitialized
        desc: 未初始化的 tensor 调用 shape 的行为

  - name: Tensor.reshape
    location: onns_api/pybind/tensor.cpp:210
    signature: "reshape(self, new_shape: List[int]) -> Tensor"
    description: 改变 tensor 的 shape
    tag: mutation  # 或 utility,取决于是否原地(见 open_questions)
    difficulty: medium
    scenarios:
      - id: happy_same_total
        desc: 元素总数相等的合法 reshape
      - id: invariant_data_order
        desc: reshape 后数据顺序保持不变
      - id: exception_shape_mismatch
        desc: 元素总数不匹配时抛 ValueError

open_questions:
  - id: q1
    api: Tensor.reshape
    question: reshape 是原地修改(返回 self)还是返回新对象?这决定 tag 归属和是否需要测试原对象不变
    priority: high
    suggested_resolution: 需要读实现或问领域专家
  - id: q2
    api: Tensor.shape
    question: 空 shape(shape=[])是否是合法的 scalar tensor?
    priority: medium

split_plan:
  strategy: by_tag
  rationale: 共 10 个 API 跨 3 个 tag,按 tag 拆分便于 generate_test 阶段套用统一策略
  batches:
    - batch_id: tensor_query
      tag: query
      apis: [Tensor.shape, Tensor.dtype, Tensor.ndim]
    - batch_id: tensor_mutation
      tag: mutation
      apis: [Tensor.reshape, Tensor.fill_]
    - batch_id: tensor_construct
      tag: construct
      apis: [create_tensor, Tensor.zeros, Tensor.ones]

notes: |
  (可选)自由文本,记录扫描过程中发现的异常、未解决的问题、
  或对后续 generate_test 阶段的建议。例如:
  - 参考样例不足 3 个,只找到 2 个
  - 发现 Tensor 类有一些 dunder 方法(__add__, __mul__)未列入,
    建议单独按算子重载规划

## 产出位置
将产出的 YAML 保存到 test_ai/generated_tests/pilot/<module_name>/plan.yaml。

## 质量自检清单
在输出 YAML 之前,自查以下几点:
- [ ] 每个 API 都有唯一 tag(没有"query/utility"这种模糊分类)
- [ ] 每个 scenario 都具体到能直接写测试的程度
- [ ] open_questions 不超过 3 个,且都是实质性问题
- [ ] split_plan 的 batches 覆盖了 apis 中的所有 API,没有遗漏
- [ ] references 里的样例是真实存在的文件(用 serena/file read 确认过)
- [ ] 不确定的事项放在 open_questions,而不是瞎猜填在 apis 里





# 简化版

---
purpose: 扫描指定 module 的 API,产出测试计划 YAML,供 generate_test 阶段使用
version: 0.1
last_updated: 2026-04-23
stage: 1 of 3 (plan → generate_test → generate_report)
output: test_ai/generated_tests/pilot/<module>/plan.yaml
---

<!-- CHANGELOG
- v0.1 (2026-04-23): 首版
-->

# Plan Prompt: Module 测试规划

为指定 module 产出测试计划 YAML。**本阶段不生成测试代码**。

## 输入

- `module`: 待测类名(如 Tensor)
- `repo_path`: 代码库路径

## 执行步骤

### 1. 扫描 API 清单

用 serena 定位 module,列出公开 API(跳过 `_` 开头的私有成员)。
每个 API 收集:全限定名、文件:行号、签名、docstring、一句话功能。

### 2. 找 3 个参考样例

按优先级查找:
1. `test_ai/generated_tests/golden/` 下同 module 或同 tag 的样例
2. 项目现有测试目录(如 `pybind/test/`)下相似测试

**找不到 3 个不要凑数**,如实列出并说明。

### 3. 分类打 tag

每个 API 恰好一个 tag:

- **query**:只读,不改状态 (e.g., `tensor.shape`)
- **construct**:造新对象 (e.g., `create_tensor`)
- **mutation**:原地改对象 (e.g., `tensor.fill_`)
- **io**:加载/保存 (e.g., `save_tensor`)
- **validation**:校验输入/状态 (e.g., `check_shape`)
- **utility**:纯工具函数,无副作用 (e.g., `tensor.to_numpy`)

**易混淆点**(必须用 serena 读实现确认,不凭名字猜):
- `reshape`/`transpose`:返回新对象 → utility;原地 → mutation
- `copy`/`clone` → construct
- 不确定的放 `open_questions`,不强行分类

### 4. 规划 scenarios

每个 API 列出该覆盖的 scenarios。要求:
- **每个 scenario 具体到能直接对应一个测试函数**
  - ✅ `空 shape (shape=[]) 应抛 ValueError`
  - ❌ `测试异常情况`
- 参考数量:query/utility 3-5;construct 4-6;mutation 5-7;io 4-6;validation 4-6

### 5. 列出 open_questions

**最多 3 个**,按优先级排。只提**实质性歧义**:
- API 语义(是否原地?非法输入抛什么?)
- 不变量定义
- fixture 依赖

**不提**:从签名可读的、hypothetical 的、一般编程知识。

### 6. 决定 split_plan

- ≤ 6 个 API:不拆
- 7-15:按 tag 拆
- > 15:按 tag 拆 + 同 tag 内 > 7 再按数量细拆

## 输出格式

严格按下面 YAML 输出,不要 markdown 包裹:

\`\`\`yaml
module: Tensor

references:
  - path: pybind/test/snnx/test_tensor.py
    rationale: 同 module 现有测试,覆盖 query 场景
    relevant_tags: [query, construct]

apis:
  - name: Tensor.shape
    location: onns_api/pybind/tensor.cpp:142
    signature: "shape(self) -> List[int]"
    tag: query
    scenarios:
      - happy_multi_dim: 1D/2D/3D tensor 返回正确维度列表
      - boundary_empty: shape=[] 的 scalar tensor 行为(见 q2)
      - exception_uninitialized: 未初始化 tensor 调用 shape

  - name: Tensor.reshape
    location: onns_api/pybind/tensor.cpp:210
    signature: "reshape(self, new_shape: List[int]) -> Tensor"
    tag: mutation  # 待确认,见 q1
    scenarios:
      - happy_same_total: 元素数相等的合法 reshape
      - invariant_data_order: reshape 后数据顺序不变
      - exception_size_mismatch: 元素数不匹配抛 ValueError

open_questions:
  - q1: Tensor.reshape 是原地修改还是返回新对象?影响 tag 归属
  - q2: 空 shape 是否是合法的 scalar tensor?

split_plan:
  strategy: by_tag
  batches:
    - id: tensor_query
      apis: [Tensor.shape, Tensor.dtype]
    - id: tensor_mutation
      apis: [Tensor.reshape, Tensor.fill_]

notes: (可选)扫描中发现的异常 / 对 generate_test 的建议
\`\`\`

## 自检

输出前确认:
- 每个 API 有唯一 tag(无"query/utility"模糊分类)
- 每个 scenario 能直接转成测试函数
- open_questions ≤ 3 且都是实质问题
- split_plan.batches 覆盖 apis 中所有 API,无遗漏
- references 中的文件真实存在(已用工具确认)






# 最小可用版

---
purpose: 扫描 module 的 API,产出测试计划 YAML
version: 0.0.1-mvp
---

# Plan Prompt (MVP)

为指定 module 产出测试计划。**本阶段不生成测试代码**。

## 步骤

1. 用 serena 列出 module 下所有公开 API
2. 对每个 API 打 tag:query / construct / mutation / io / validation / utility
3. 每个 API 列出 3-5 个测试 scenario
4. 列出最多 3 个需人工确认的问题

## 输出 YAML

保存到 test_ai/generated_tests/pilot/<module>/plan.yaml

\`\`\`yaml
module: Tensor
apis:
  - name: Tensor.shape
    location: <file:line>
    signature: <sig>
    tag: query
    scenarios:
      - <scenario 1>
      - <scenario 2>

open_questions:
  - <q1>
  - <q2>
\`\`\`
