---
purpose: 对一个完整 module 的测试生成和执行结果进行汇总,产出面向领导的 review 报告
version: 0.1
last_updated: 2026-04-23
stage: 3 of 3 (plan → generate_test → generate_report)
input: module_dir(包含 plan.yaml 和生成的 test_*.py 文件)
output: test_ai/generated_tests/pilot/<module>/report.md
---

<!-- CHANGELOG
- v0.1 (2026-04-23): 首版。module-level 汇总,含 gitnexus 影响分析,pytest 结果可选
-->

# Generate Report Prompt

对一个完整 module 的测试生成与执行过程,产出一份面向领导的技术汇报。

## 输入

- `module_dir`: 包含 `plan.yaml` 和 `test_*.py` 的目录(如 `test_ai/generated_tests/pilot/snnxtensor/`)
- `pytest_result_path`(可选): pytest 的执行结果文件,若无则跳过对应章节

## 执行步骤

### 1. 收集数据(必须用工具,禁止编造)

- 读 `module_dir/plan.yaml`:获取 module 名、API 清单、scenarios 总数
- 读 `module_dir/test_*.py` 所有文件:统计测试函数数、skip 数、Issues 段落
- 如提供 `pytest_result_path`,读取 pytest 结果;**若未提供,跳过 pytest 相关章节,不要猜测结果**

### 2. 用 serena 查人工基线

- 在项目现有测试目录(通常是 `pybind/test/` 或类似路径)查找覆盖同 module 的测试文件
- 记录文件路径、测试函数数、覆盖的 API
- 如找不到,在报告中标注"无人工基线可对比",**不要编造基线数据**

### 3. 用 gitnexus 做影响分析

**目的**:证明 AI 测的 API 是"有价值的",不是随便测。

- 对 AI 覆盖的每个 API,用 gitnexus 的 `impact` 或 `context` 工具查其影响面(下游依赖数、参与的执行流数)
- 对人工覆盖的每个 API,做同样的分析
- 用于第四章的"覆盖质量"对比
- 如 gitnexus 工具不可用(报错或超时),在对应章节标注 "impact analysis unavailable",**不要猜测影响面数字**

### 4. 生成报告

按下方"报告结构"产出 markdown。

## 报告结构

**严格按此结构,不要增加章节,每节长度按标注控制**。

### Frontmatter(metrics 必填,数据缺失用 null 或 not_executed)

```yaml
---
module: <module 名>
timestamp: <生成时刻>
generated_by: <LLM model 名,如 gemma-4-31B>
metrics:
  apis_total: 23                    # plan 扫到的 API 总数
  apis_covered_ai: 10               # AI 覆盖的 API 数
  apis_covered_manual: 8            # 人工覆盖的 API 数 (no baseline → null)
  tests_generated_ai: 24            # AI 生成的测试函数总数
  tests_skipped_ai: 3               # AI 生成的但标了 skip 的
  tests_manual: 18                  # 人工测试数 (no baseline → null)
  pytest:
    status: passed | failed | partial | not_executed
    pass_rate: 0.83                 # not_executed → null
    coverage: 0.67                  # 未测 coverage → null
  suspected_bugs: 2                 # Issues 段落 + skip 中 mismatch 的数量
  impact_analysis:
    status: completed | unavailable
    ai_covered_impact_sum: 45       # unavailable → null
    manual_covered_impact_sum: 30   # no baseline 或 unavailable → null
---
```

### 一、概览(1 段,100 字以内)

一句话说明:对什么 module 做了什么;耗时如何;产出多少。
**避免空话**(如"顺利完成"、"效果良好"),只讲事实。

### 二、数据对比(核心,给领导看)

用表格直接呈现关键数字,不超过 2 段叙述。

**必含表格**:

| 指标 | AI | 人工 | 说明 |
|---|---|---|---|
| 覆盖 API 数 | N | M | - |
| 测试函数数 | X | Y | - |
| pytest 通过率 | a% | - | AI 产出的 pytest 结果 |
| 代码 coverage | b% | - | 如未测留空 |
| 加权影响面 | P | Q | 每个 API 的下游依赖数之和(gitnexus) |

表下 1 段结论:**AI 相对人工,覆盖了更多/更少,质量更高/相当/更低的理由**。基于数据说话。

### 三、发现的问题

结构化列出疑似 bug 和 open_questions。**每条必须可追溯到具体测试文件或源码位置**。

```markdown
#### Bug 候选 #1
- **API**: snnxtensor.xxx
- **触发条件**: ...
- **预期 vs 实际**: ...
- **复现测试**: test_snnxtensor_xxx.py::test_xxx_boundary_empty
- **置信度**: high | medium | low

#### Open Question #1
- **API**: ...
- **问题**: ...
- **来源**: plan.yaml 中 q1
```

没有发现 → 诚实写"本次未发现疑似 bug"。**不要为凑数编造**。

### 四、AI 的独特贡献

列 2-3 个具体场景:AI 覆盖了、而人工没测的 scenario。
每个场景说明:
- 是什么 scenario
- 为什么有价值(用 gitnexus 的影响面数据支持)
- 举一个具体测试函数名

**如果 AI 覆盖范围完全是人工的子集,诚实写"本次 AI 未产生独特覆盖"**。

### 五、已知不足与后续计划

列 2-4 点:
- AI 没覆盖但应覆盖的(通过 gitnexus 发现的盲区)
- 生成过程中的主要失败模式
- 下一个 module 会做什么改进

**不超过 4 点**,超出合并。

## 禁止项(三层强化之一)

- ❌ **在数据缺失时编造**:pytest 没跑就写 "pass rate 估计 80%"、人工基线没有就编数据、gitnexus 不可用就猜影响面——这是最严重的违规
- ❌ 使用"顺利"、"良好"、"整体效果不错"等主观评价词
- ❌ 把 AI 自身的"Issues encountered"段落隐去不报
- ❌ 用训练数据猜测 API 的影响面
- ❌ 添加本结构未定义的章节(如"总结展望"、"致谢")
- ❌ 超过指定的长度限制

## 必须做(三层强化之二)

- ✅ 所有数字都来自实际数据:plan.yaml、测试文件、pytest 结果、gitnexus 查询
- ✅ 每个 bug 候选都可复现(有测试函数或源码位置)
- ✅ 数据缺失时明确标注(null、not_executed、unavailable)
- ✅ "AI 独特贡献"章节必须有具体例子或诚实声明无

## 产出位置

`test_ai/generated_tests/pilot/<module>/report.md`

## 输出前自检(三层强化之三)

- [ ] 所有 metrics 字段都有值或明确的 null/not_executed/unavailable
- [ ] **没有任何数字是"估计"或"大约"出来的**(最易违反)
- [ ] **没有任何对比是在基线不存在时做的**(最易违反)
- [ ] **gitnexus 不可用时,影响面相关数据已标 unavailable**(最易违反)
- [ ] 第三章每个 bug 候选都可追溯到具体文件:行
- [ ] 第四章的"独特贡献"有具体例子 或 诚实声明无
- [ ] 报告总长度不超过 1.5 屏
- [ ] 不含"顺利"、"良好"、"大致"等主观词
