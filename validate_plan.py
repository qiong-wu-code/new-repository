#!/usr/bin/env python3
"""
validate_plan.py - 校验 plan.yaml 的格式和内容一致性

用法: python validate_plan.py <path_to_plan.yaml>
"""

import sys
import yaml
from pathlib import Path
from typing import Literal, List, Optional
from pydantic import BaseModel, Field, ValidationError

# ===== Schema 定义 =====

TAG = Literal["query", "construct", "mutation", "io", "validation", "utility"]
PRIORITY = Literal["high", "medium", "low"]

class Scenario(BaseModel):
    id: str
    desc: str
    
    # 允许 yaml 里用 "key: value" 的单键字典形式
    # 如果你的 yaml 里 scenario 是 {happy_3d: "描述..."} 这种形式,
    # 需要单独处理,我下面会说

class API(BaseModel):
    name: str
    location: str
    signature: str
    tag: TAG
    description: Optional[str] = None
    scenarios: List[dict]  # 先用 dict,后面根据实际格式收紧

class OpenQuestion(BaseModel):
    id: str
    api: str
    question: str
    priority: PRIORITY
    suggested_resolution: Optional[str] = None

class Reference(BaseModel):
    path: str
    rationale: Optional[str] = None
    selection_rationale: Optional[str] = None  # 兼容两种字段名
    relevant_tags: Optional[List[TAG]] = None

class Batch(BaseModel):
    id: Optional[str] = None
    batch_id: Optional[str] = None  # 兼容两种字段名
    tag: Optional[TAG] = None
    apis: List[str]

class SplitPlan(BaseModel):
    strategy: str
    rationale: Optional[str] = None
    batches: List[Batch]

class Plan(BaseModel):
    module: str
    apis: List[API]
    references: Optional[List[Reference]] = None
    open_questions: List[OpenQuestion] = Field(max_length=3)
    split_plan: Optional[SplitPlan] = None
    notes: Optional[str] = None

# ===== 辅助函数 =====

def check_yaml_syntax(path: str) -> Optional[dict]:
    """检查 YAML 能否解析,返回解析后的 dict 或 None"""
    try:
        with open(path) as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"❌ YAML 语法错误,无法解析:\n")
        print(f"{e}\n")
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            print(f"错误位置:第 {mark.line + 1} 行,第 {mark.column + 1} 列")
            with open(path) as f:
                lines = f.readlines()
            start = max(0, mark.line - 2)
            end = min(len(lines), mark.line + 3)
            print(f"\n附近内容:")
            for i in range(start, end):
                prefix = ">>> " if i == mark.line else "    "
                print(f"{prefix}{i+1}: {lines[i].rstrip()}")
        return None

def check_cross_references(plan: Plan) -> List[str]:
    """跨字段一致性检查"""
    issues = []
    
    all_api_names = {api.name for api in plan.apis}
    
    # 检查 split_plan.batches 里引用的 API 是否都存在
    if plan.split_plan:
        for batch in plan.split_plan.batches:
            batch_id = batch.id or batch.batch_id or "(unnamed)"
            for api_name in batch.apis:
                if api_name not in all_api_names:
                    issues.append(
                        f"split_plan.batches[{batch_id}] 引用了不存在的 API: {api_name}"
                    )
    
    # 检查 open_questions 里的 api 字段是否真实
    for q in plan.open_questions:
        if q.api not in all_api_names:
            issues.append(
                f"open_questions[{q.id}] 引用了不存在的 API: {q.api}"
            )
    
    # 检查是否有 API 分配了 tag 但不在任何 batch 里(可能漏了)
    if plan.split_plan:
        apis_in_batches = set()
        for batch in plan.split_plan.batches:
            apis_in_batches.update(batch.apis)
        missing = all_api_names - apis_in_batches
        if missing:
            issues.append(
                f"以下 API 未被分配到任何 batch: {sorted(missing)}"
            )
    
    return issues

# ===== 主流程 =====

def main():
    if len(sys.argv) != 2:
        print("用法: python validate_plan.py <path_to_plan.yaml>")
        sys.exit(1)
    
    path = sys.argv[1]
    if not Path(path).exists():
        print(f"❌ 文件不存在: {path}")
        sys.exit(1)
    
    # 第一层: YAML 语法
    data = check_yaml_syntax(path)
    if data is None:
        sys.exit(1)
    
    # 第二层: Schema 校验
    try:
        plan = Plan(**data)
    except ValidationError as e:
        print("❌ Schema 校验失败:\n")
        for err in e.errors():
            loc = " -> ".join(str(x) for x in err['loc'])
            print(f"  [{loc}] {err['msg']}")
            if 'input' in err and err['input'] is not None:
                input_str = str(err['input'])
                if len(input_str) > 80:
                    input_str = input_str[:80] + "..."
                print(f"    实际值: {input_str}")
        sys.exit(1)
    
    # 第三层: 跨字段一致性
    issues = check_cross_references(plan)
    if issues:
        print("⚠️  一致性检查发现问题:\n")
        for issue in issues:
            print(f"  - {issue}")
        sys.exit(1)
    
    # 全部通过
    print(f"✅ 所有检查通过")
    print(f"   module: {plan.module}")
    print(f"   APIs 数量: {len(plan.apis)}")
    print(f"   open_questions: {len(plan.open_questions)}")
    if plan.split_plan:
        print(f"   batches: {len(plan.split_plan.batches)}")

if __name__ == "__main__":
    main()
