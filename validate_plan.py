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

# 跑校验
if __name__ == "__main__":
    path = sys.argv[1]
    try:
        plan = Plan(**yaml.safe_load(open(path)))
        print("✅ All checks passed")
    except Exception as e:
        print(f"❌ Validation failed:\n{e}")
        sys.exit(1)
