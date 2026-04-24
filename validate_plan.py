from pydantic import BaseModel, Field
from typing import Literal, List
import yaml
import sys

# 定义合法结构
class Scenario(BaseModel):
    id: str
    desc: str

class API(BaseModel):
    name: str
    location: str
    signature: str
    tag: Literal["query", "construct", "mutation", "io", "validation", "utility"]
    scenarios: List[Scenario]

class Plan(BaseModel):
    module: str
    apis: List[API]
    open_questions: List[str] = Field(max_length=3)

import yaml
import sys

def check_yaml_syntax(path: str) -> bool:
    """先检查 YAML 本身能否解析,再做 schema 校验"""
    try:
        with open(path) as f:
            yaml.safe_load(f)
        return True
    except yaml.YAMLError as e:
        print(f"❌ YAML 语法错误,无法解析:\n")
        print(f"{e}\n")
        
        # 如果能拿到行号,打印上下文
        if hasattr(e, 'problem_mark'):
            mark = e.problem_mark
            print(f"错误位置:第 {mark.line + 1} 行,第 {mark.column + 1} 列")
            
            # 打印错误行上下文
            with open(path) as f:
                lines = f.readlines()
            start = max(0, mark.line - 2)
            end = min(len(lines), mark.line + 3)
            print(f"\n附近内容:")
            for i in range(start, end):
                prefix = ">>> " if i == mark.line else "    "
                print(f"{prefix}{i+1}: {lines[i].rstrip()}")
        
        return False

if __name__ == "__main__":
    path = sys.argv[1]
    if not check_yaml_syntax(path):
        sys.exit(1)
    try:
        plan = Plan(**yaml.safe_load(open(path)))
        print("✅ All checks passed")
    except Exception as e:
        print(f"❌ Validation failed:\n{e}")
        sys.exit(1)
