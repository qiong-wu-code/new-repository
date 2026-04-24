---
purpose: 根据 plan.yaml 中指定的 batch,为该 batch 内的 API 生成 pytest 测试文件
version: 0.1.1
last_updated: 2026-04-23
stage: 2 of 3 (plan → generate_test → generate_report)
input: plan_path + batch_id
output: test_ai/generated_tests/pilot/<module>/test_<module>_<tag>.py
---

<!-- CHANGELOG
- v0.1.1 (2026-04-23): 修订。类名去掉 tag 后缀(对齐项目风格);加"单一职责"要求;精简重复表述
- v0.1 (2026-04-23): 首版 MVP
-->

# Generate Test Prompt

根据 plan.yaml 中指定 batch 的内容,生成 pytest 测试文件。

## 输入

- `plan_path`: plan.yaml 的路径
- `batch_id`: 要处理的 batch ID(如 `snnxtensor_query`)

## 执行步骤

1. **读取 plan**:从 `plan_path` 定位 `split_plan.batches` 中 id 匹配 `batch_id` 的项,获取 `apis` 列表和 `tag`
2. **聚合 API 详情**:根据 batch 中的 API 名字,从 `apis` 顶层字段中匹配,获取完整详情
3. **读取参考样例**:如果 plan.yaml 的 `references` 字段有内容,用 serena 读取并学习风格
4. **生成测试代码**:按下方风格规范生成

## 风格规范(核心)

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
    
    def test_<api_short>_1(self, <fixture_name>):
        """
        Test <api> api
        
        <具体测试目的,一句话说明在验证什么行为>
        """
        # test body

    # more tests...
```

### 命名规范

- **类名**:`Test<Module>`(不带 tag 后缀)。同一 module 的不同 tag 共用类名,靠文件名区分
- **测试函数**:`test_<api_short>_<序号>`,序号从 1 开始
  - `<api_short>`:去掉 module 前缀,如 `snnxtensor.get_name` → `get_name`
  - 同一 API 的不同 scenario 用连续序号:`test_get_name_1` / `test_get_name_2` / ...

### Docstring 规范

**函数 docstring 必须两段式**(严格遵守):

```
"""
Test <api> api

<一句话说明在验证什么行为/场景,英文>
"""
```

第二部分要**具体描述验证目标**,不是机械复述:

- ❌ `Test happy path`(太泛)
- ❌ `Create a tensor with shape [2,3]`(只说做了什么,没说验证什么)
- ✅ `Test whether get_name returns the default empty string when no name is set`
- ✅ `Test that set_name rejects non-string input with TypeError`

### 测试函数的单一职责

**每个测试函数只验证一个行为**。不要在一个函数里测多个独立场景。

- ❌ 一个 `test_create_tensor_1` 里又测 shape 又测 dtype 又测 device
- ✅ `test_create_tensor_1` 测 shape, `test_create_tensor_2` 测 dtype, `test_create_tensor_3` 测 device

多个 assert 可以,但它们应该共同验证同一个行为。

### Fixture

- 放在 class 内部(本项目当前无 conftest.py)
- `scope='function'` 显式声明
- setup 在 `yield` 前,teardown 在 `yield` 后
- teardown 至少 `del obj`,有资源要释放

### 断言与异常

- 等值:`assert x == y`
- 异常:`with pytest.raises(SomeError):`(v0.1 不用 `match`)
- 跳过:`@pytest.mark.skip(reason="...")`,理由写清楚

### Imports

只 import 实际用到的符号。不用 `import *`,不 import 未使用的 module。

## 禁止项

以下是 LLM 常见坏习惯,明确禁止:

- ❌ Common sense 注释:`# create a tensor`、`# check the result`
- ❌ 占位代码:`# TODO`、`# FIXME`、`pass  # placeholder`
- ❌ 防御性废话:`assert obj is not None` 后立刻用 `obj.attr`
- ❌ 调试残留:`print()`、`breakpoint()`
- ❌ 参数化工具:`pytest.mark.parametrize`(v0.1 约束,对齐项目现状)
- ❌ `match` 参数:`pytest.raises(X, match=...)`(v0.1 约束)
- ❌ 自行增加 plan 中没有的 scenario
- ❌ Docstring 里复述函数名或参数类型

## 必须做

- ✅ plan 中的每个 scenario 对应至少一个测试函数
- ✅ 对应 open_question 未解决的 scenario:测试代码照写,但加 `@pytest.mark.skip(reason="See open_question: <q_id>")`
- ✅ setup/teardown 对称——创建的资源要释放

## 产出位置

保存到 `test_ai/generated_tests/pilot/<module>/test_<module>_<tag>.py`,文件名从 plan 的 `module` 和 batch 的 `tag` 拼出。

例:module=snnxtensor, tag=query → `test_snnxtensor_query.py`

## 生成过程中遇到问题怎么办

**不要猜,要标注**。

- **plan 的 scenario 描述不够写测试**(不知道预期行为):在文件末尾 `# Issues encountered` 段落中说明
- **发现 API 签名和实现可能不一致**:写一个跳过的测试 `@pytest.mark.skip(reason="Suspected API/impl mismatch: <details>")`,并在文件末尾 Issues 段落详述
- **plan 中某个 scenario 看起来不合理**:照写,但在函数 docstring 末尾加 `NOTE: <你的疑虑>`

文件末尾的 Issues 段落格式:

```python
# ============================================================
# Issues encountered during generation
# ============================================================
# - scenario <id>: 描述不清,需要补充...
# - API <name>: 疑似签名/实现冲突,建议人工确认
```

这些会在 generate_report 阶段被整理。

## 输出前自检

- [ ] 每个 plan 中的 scenario 都有对应测试(数量一致)
- [ ] class 名是 `Test<Module>`(不含 tag)
- [ ] 每个函数有两段式 docstring,第二段具体描述验证目标
- [ ] 每个函数只验证一件事(单一职责)
- [ ] fixture 有 setup/yield/teardown 对称结构
- [ ] 没有 parametrize、没有 match(v0.1 约束)
- [ ] open_question 涉及的测试标了 skip
- [ ] imports 干净,无未使用的 import
- [ ] 
