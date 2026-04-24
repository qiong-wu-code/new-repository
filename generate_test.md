---
purpose: 根据 plan.yaml 中指定的 batch,为该 batch 的 API 生成 pytest 测试文件
version: 0.3
last_updated: 2026-04-23
stage: 2 of 3 (plan → generate_test → generate_report)
input: plan_path + batch_id
output: test_ai/generated_tests/pilot/<module>/test_<module>_<tag>.py
---

<!-- CHANGELOG
- v0.3 (2026-04-23): 函数命名改用 scenario id 替代序号(直接复用 plan.yaml 的 scenario.id)
- v0.2 (2026-04-23): 显式要求 serena 读参考样例;加"禁止凭训练数据编造"硬约束;精简冗余
- v0.1.1 (2026-04-23): 类名去掉 tag 后缀;加单一职责要求
- v0.1 (2026-04-23): 首版 MVP
-->

# Generate Test Prompt

根据 plan.yaml 中指定 batch 的内容,生成 pytest 测试文件。

## 输入

- `plan_path`: plan.yaml 的路径
- `batch_id`: 要处理的 batch ID(如 `snnxtensor_query`)

## 执行步骤

1. **读 plan**:从 `plan_path` 定位 `split_plan.batches` 中 id 匹配 `batch_id` 的项,获取 `apis` 列表和 `tag`。从 `apis` 顶层字段聚合每个 API 的完整详情(含其 scenarios)。

2. **读参考样例(必须用 filesystem/serena,禁止凭空推断)**:
   - plan.yaml 的 `references` 字段中列出了参考文件路径
   - 对每个路径,实际读取文件内容,学习命名、fixture、docstring、断言风格
   - 如某路径无法访问,在文件末尾 Issues 段落报告,**不要用训练数据补全想象中的内容**

3. **生成测试代码**:按下方风格规范生成。

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

- **类名**:`Test<Module>`(不带 tag)。同一 module 的不同 tag 分文件,共用类名
- **函数名**:`test_<api_short>_<scenario_id>`
  - `<api_short>`:去掉 module 前缀。如 `snnxtensor.get_name` → `get_name`
  - `<scenario_id>`:**直接使用** plan.yaml 中该 scenario 的 `id` 字段,不要改动或重新编号
  - 例:`snnxtensor.get_name` + scenario id `happy_default` → `test_get_name_happy_default`

### Docstring(两段式,严格遵守)

```
"""
Test <api> api

<英文,一句话说明在验证什么行为/场景>
"""
```

第二段要**具体描述验证目标**:

- ❌ `Test happy path` / `Create a tensor with shape [2,3]`
- ✅ `Test that set_name rejects non-string input with TypeError`

### 单一职责

**每个测试函数只验证一个行为**。多个 assert 可以,但应共同支撑同一个验证目标。

不要一个函数里既测 shape 又测 dtype 又测 device——拆成三个。

### Fixture

- 放在 class 内部(本项目当前无 conftest.py,不要假设其存在)
- `scope='function'` 显式声明
- `yield` 分隔 setup/teardown,teardown 至少 `del`

### 断言与异常

- 等值:`assert x == y`
- 异常:`with pytest.raises(SomeError):`(**不用 `match` 参数**)
- 跳过:`@pytest.mark.skip(reason="...")`,理由明确

## 禁止项

- ❌ Common sense 注释(`# create a tensor`)、占位代码(`# TODO`、`pass`)、调试残留(`print`)
- ❌ 防御性废话(`assert obj is not None` 后立刻用 `obj.attr`)
- ❌ 未使用的 import、`import *`
- ❌ `pytest.mark.parametrize`(v0.3 约束)
- ❌ `pytest.raises(X, match=...)` 的 `match` 参数(v0.3 约束)
- ❌ 自行增加 plan 中没有的 scenario
- ❌ 修改 scenario id 或用序号替代 scenario id
- ❌ Docstring 里复述函数名或参数类型
- ❌ **凭训练数据编造 API 签名、fixture、helper**——不确定时用 serena 确认,或写 skip 并在 Issues 中报告

## 遇到问题怎么办

**不要猜,要标注**:

- **plan 的 scenario 描述不足以写测试** → 文件末尾 Issues 段落记录
- **疑似 API 签名/实现不一致** → 写 `@pytest.mark.skip(reason="Suspected API/impl mismatch: <details>")`,Issues 段落详述
- **plan 中某 scenario 看起来不合理** → 照写,docstring 末尾加 `NOTE: <疑虑>`

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
- ✅ plan 中标了 open_question 的 scenario 对应测试加 `@pytest.mark.skip(reason="See open_question: <q_id>")`,代码仍要写全

## 输出前自检

- [ ] 每个 scenario 都有对应测试(通过函数名后缀比对 plan 中的 scenario id)
- [ ] class 名是 `Test<Module>`(不含 tag)
- [ ] 每个函数有两段式 docstring,第二段具体描述验证目标
- [ ] 每个函数单一职责
- [ ] 没有 parametrize、没有 match、没有未使用 import
- [ ] open_question 涉及的测试已标 skip
- [ ] Issues 段落(如有)正确记录了未解决的问题

