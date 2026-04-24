---
purpose: 根据 plan.yaml 中指定的 batch,为该 batch 的 API 生成 pytest 测试文件
version: 0.4
last_updated: 2026-04-23
stage: 2 of 3 (plan → generate_test → generate_report)
input: plan_path + batch_id
output: test_ai/generated_tests/pilot/<module>/test_<module>_<tag>.py
---

<!-- CHANGELOG
- v0.4 (2026-04-23): 加"断言强度"规则(修复 get_information 类敷衍);恢复 imports 独立段;
                     强调 scenario desc 必须被真正验证;补 docstring 反例
- v0.3 (2026-04-23): 函数命名改用 scenario id
- v0.2 (2026-04-23): serena 硬约束;精简冗余
- v0.1.1 (2026-04-23): 类名去 tag;加单一职责
- v0.1 (2026-04-23): 首版 MVP
-->

# Generate Test Prompt

根据 plan.yaml 中指定 batch 的内容,生成 pytest 测试文件。

## 输入

- `plan_path`: plan.yaml 的路径
- `batch_id`: 要处理的 batch ID(如 `snnxtensor_query`)

## 执行步骤

1. **读 plan**:从 `plan_path` 定位 `split_plan.batches` 中 id 匹配 `batch_id` 的项,获取 `apis` 和 `tag`。从 `apis` 顶层字段聚合每个 API 的完整详情(含其 scenarios)。

2. **读参考样例(必须用 filesystem/serena,禁止凭空推断)**:
   - plan.yaml 的 `references` 字段列出了参考文件路径
   - 对每个路径,实际读取文件内容,学习**命名、fixture、docstring、断言风格**
   - 参考样例是本项目现有的真实测试,**其风格优先级高于本 prompt 的抽象描述**(硬约束除外)
   - 如某路径无法访问,在文件末尾 Issues 段落报告,**不要用训练数据补全想象中的内容**

3. **理解每个 API 的返回值结构(关键步骤)**:
   - 对于返回容器(dict/list/tuple)或复杂对象的 API,**必须用 serena 的 `get_symbol(..., include_body=True)` 读实现**
   - 明确返回值里应该有什么字段、什么值
   - 这是写出有深度断言的前提,不能跳过

4. **生成测试代码**:按下方风格规范生成。

## 风格规范

### 文件结构模板

```python
"""
Test <Module> <tag> APIs

Covered APIs: <list of api names from this batch>
"""

import pytest
# only what you actually use


class Test<Module>:
    """Test <Module> API Class
    
    This Class is created to test <Module> APIs using pytest.
    
    The <fixture_name> method is a fixture, which returns a <module> object 
    used by every function in this class.
    """
    
    @pytest.fixture(scope='function')
    def <fixture_name>(self):
        obj = ...
        yield obj
        del obj
    
    def test_<api_short>_<scenario_id>(self, <fixture_name>):
        """
        Test <api> api
        
        <具体测试目的,一句话说明在验证什么行为>
        """
        # test body
```

### 命名

- **类名**:`Test<Module>`(不带 tag)
- **函数名**:`test_<api_short>_<scenario_id>`
  - `<api_short>`:去掉 module 前缀。如 `snnxtensor.get_name` → `get_name`
  - `<scenario_id>`:**直接使用** plan.yaml 中该 scenario 的 `id` 字段,不得修改
  - 例:`get_name` + scenario id `happy_default` → `test_get_name_happy_default`

### Docstring(两段式)

```
"""
Test <api> api

<英文,具体描述验证目标>
"""
```

第二段**必须具体描述在验证什么**,不是机械复述 API 名或 scenario id:

- ❌ `Test happy path`(太泛)
- ❌ `Create a tensor with shape [2,3]`(只说做了什么,没说验证什么)
- ❌ `Test get_name api works`(没信息量)
- ✅ `Test that get_name returns the default empty string when no name is set`
- ✅ `Test that set_name rejects non-string input with TypeError`

### 断言强度(重要)

断言必须**验证具体的预期值或结构**,不能只验证类型或存在性。

**规则**:

- **返回容器(dict/list/tuple)**:必须断言结构(有哪些 key/元素)和至少部分值,不能只断 `isinstance`
- **返回对象**:至少断言 2-3 个期望属性,不能只断 `is not None`
- **返回简单值(int/str/bool)**:直接断言等于预期值

**反例与正例**:

```python
# ❌ 弱断言:空 dict 也能过
assert isinstance(result, dict)

# ✅ 强断言:验证结构 + 值
assert isinstance(result, dict)
assert 'name' in result and 'shape' in result and 'dtype' in result
assert result['name'] == obj.get_name()
```

```python
# ❌ 弱断言
assert tensor.shape is not None

# ✅ 强断言
assert tensor.shape == [2, 3, 4]
```

**如果不清楚返回值里该有什么**:用 serena 读实现(见执行步骤 3),**不许只断言类型完事**。

### 单一职责

每个测试函数只验证一个行为。多个 assert 可以,但应共同支撑同一个验证目标。

不要一个函数里既测 shape 又测 dtype 又测 device——拆成三个。

### Scenario 必须被真正验证

每个测试函数的**实际代码逻辑**必须验证 plan 中对应 scenario 的 `desc` 字段所描述的内容。

- ❌ scenario desc 是 `get_name 返回 set_name 设置的值`,但测试只做了 `assert isinstance(result, str)`
- ✅ scenario desc 是 `get_name 返回 set_name 设置的值`,测试做了 `tensor.set_name('foo'); assert tensor.get_name() == 'foo'`

**换句话说**:测试不是"挂一个能跑的壳子",而是"真正验证 scenario 声称的行为"。

### Imports

- 只 import 实际用到的符号
- 不用 `import *`
- 标准库和第三方分两段,`pytest` 单独一行

### Fixture

- 放在 class 内部(本项目当前无 conftest.py,不要假设其存在)
- `scope='function'` 显式声明
- `yield` 分隔 setup/teardown,teardown 至少 `del`

### 断言异常

- 等值:`assert x == y`
- 异常:`with pytest.raises(SomeError):`(**不用 `match` 参数**)
- 跳过:`@pytest.mark.skip(reason="...")`,理由明确

## 禁止项

- ❌ **只断言类型或 `is not None` 就完事**(见断言强度规则)
- ❌ Common sense 注释(`# create a tensor`)、占位代码(`# TODO`、`pass`)、调试残留(`print`)
- ❌ 防御性废话(`assert obj is not None` 后立刻用 `obj.attr`)
- ❌ 未使用的 import、`import *`
- ❌ `pytest.mark.parametrize`(v0.4 约束)
- ❌ `pytest.raises(X, match=...)` 的 `match` 参数(v0.4 约束)
- ❌ 自行增加 plan 中没有的 scenario
- ❌ 修改 scenario id 或用序号替代 scenario id
- ❌ Docstring 里复述函数名或参数类型
- ❌ **凭训练数据编造 API 签名、fixture、helper**——不确定时用 serena 确认,或写 skip 并在 Issues 报告

## 遇到问题怎么办

**不要猜,要标注**:

- **plan 的 scenario 描述不足以写测试** → 文件末尾 Issues 段落记录
- **疑似 API 签名/实现不一致** → 写 `@pytest.mark.skip(reason="Suspected API/impl mismatch: <details>")`,Issues 段落详述
- **用 serena 读了实现仍不清楚期望值** → 写测试但加 `NOTE: <疑虑>` 到 docstring 末尾

文件末尾 Issues 段落格式:

```python
# ============================================================
# Issues encountered during generation
# ============================================================
# - scenario <id>: <问题描述>
# - API <name>: <问题描述>
```

## 产出位置

`test_ai/generated_tests/pilot/<module>/test_<module>_<tag>.py`

例:module=snnxtensor, tag=query → `test_snnxtensor_query.py`

## 必须覆盖

- ✅ plan 中的每个 scenario 至少对应一个测试函数,函数名后缀严格等于 scenario id
- ✅ 每个测试函数的代码实际验证 scenario desc 描述的行为(不是挂壳)
- ✅ plan 中标了 open_question 的 scenario 对应测试加 `@pytest.mark.skip(reason="See open_question: <q_id>")`,代码仍要写全

## 输出前自检

- [ ] 每个 scenario 都有对应测试函数(函数名后缀 = scenario id)
- [ ] **每个测试的断言不是只有 `isinstance` 或 `is not None`**(最易忽略)
- [ ] **每个测试的代码逻辑真正验证了 scenario desc,不是挂壳**(最易忽略)
- [ ] class 名是 `Test<Module>`(不含 tag)
- [ ] 每个函数有两段式 docstring,第二段具体描述验证目标
- [ ] 每个函数单一职责
- [ ] 返回容器的 API:断言了结构和至少部分值(不只 `isinstance`)
- [ ] 没有 parametrize、没有 match、没有未使用 import
- [ ] open_question 涉及的测试已标 skip
- [ ] Issues 段落(如有)正确记录了未解决的问题
