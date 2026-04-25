你是一名资深 Python 工程师。你将构建一个由三个独立 CLI 脚本组成的小型 skill,
用来解析模型量化回归测试结果,并最终输出一份 xlsx 报告。我会分三轮把规格
告诉你,每轮一个脚本。所有脚本都要遵守下面这套通用规则。

== 编码规则 ==
- Python 3.10+,只用标准库,例外:第三个脚本可以用 openpyxl。
- 每个脚本都自包含,可以直接 `python scripts/<名字>.py --help` 跑起来。
- 用 argparse;必填参数加 required=True;统一支持 --verbose/-v。
- 所有文件读写用 utf-8、errors='replace'(日志里有乱码是常态)。
- 单个模型出错绝不能让整个脚本崩溃。每个模型的异常单独 catch,
  记到该模型的 notes 字段。一条坏记录不能拖垮其他模型。
- JSON 输出用 indent=2、ensure_ascii=False,方便人看和 diff。
- 进度信息打到 stderr,不要打到 stdout(stdout 留给管道)。
- 退出码:正常或仅有 warning => 0;参数错误/用法错误 => 2。
- 脚本顶部写一段 docstring,说明这个脚本干什么、做了哪些稳定性取舍。
- 用 type hints。开头加 `from __future__ import annotations`。
- 不要发起任何网络请求,不要起子进程,不要用多线程。

== conversion 判定规则 ==

判定逻辑【目前】只看一条规则:最新 log 里出现
`^Traceback \(most recent call last\):\s*$` 这一行 => FAIL,否则 PASS。

但要注意:这套规则【以后大概率会扩充】,因为不是所有失败都会留下
Python traceback —— 比如 SDK 段错误、被 kill 掉、写出非法产物
但进程 0 退出之类的情况。所以在写代码时:

1. 把判定逻辑集中到一个独立函数里,签名形如:
     def classify_log(log_text: str) -> tuple[str, str]:
         """返回 (status, evidence)。status ∈ {"PASS","FAIL"};
         evidence 是触发该判定的证据文本(FAIL 时是 traceback 块,
         PASS 时是空串)。"""
2. 函数内部用一个【按顺序检查的规则列表】,每条规则一个小函数,
   返回 None 或 (匹配到的证据文本)。任一规则命中就 FAIL,全没命中
   就 PASS。当前的列表里只有 traceback 一条规则。
3. 在该函数上方写一段醒目的注释,标题就叫
   "FAILURE DETECTION RULES — extend here",写明:
     - 当前规则:traceback 出现
     - 增加新规则的方法:在 RULES 列表追加一个 (名字, 检测函数)
     - 强调"warning"/"error"/"fail" 字面词【目前不算 FAIL】,
       因为成功 case 也常打这些词;以后要加这类规则必须用更精确的
       上下文(比如"^FATAL: " 行首 + 大写)而不是裸字面匹配。
4. JSON 输出里 FAIL 记录加一个新字段 "fail_reason",值是命中的规则名
   (目前固定为 "traceback")。这样以后日志里能看出是哪条规则命中的。

不要写"插件加载机制""动态注册"之类的过度设计。就是一个 list,
里面放 tuple,简单直接。


== 领域背景(每个脚本都要用,请仔细看) ==
- 一次回归跑测的结果会落在一个根目录下,根目录里有 100+ 个模型子目录。
- 每个模型子目录的命名形如 `01-01_YOLO_v4_1`,正则:
    ^(?P<id>\d+[-_]\d+)_(?P<name>.+)$
  其中 id 部分就是后面要用的 model_id,后缀部分是 model_name。
- 完整的目录名 `<model_id>_<model_name>` 在用户场景下是【唯一】的。
- 每个模型目录下,conversion 日志的位置固定是:
    Convertion_result/convert/.log/*.log
  注意:`Convertion` 是用户那边历史拼写错误,目录就叫这个名字,
  不要"自作主张"改成 `Conversion`。
- 这个 .log 目录下可能有多个 .log 文件。永远取 mtime 最新的那个,
  不要按文件名排序。
- conversion 的判定规则是【纯规则】:
    FAIL  = 最新那份 log 里出现了正则 `^Traceback \(most recent call last\):\s*$` 的行
    PASS  = 没有出现
    NO_LOG = 模型目录存在,但 .log 目录下没有日志文件
  日志里出现的字面词 "warning" / "error" / "fail" 一律不算 FAIL,只有
  Traceback 标记算。这一点非常关键,不要自己加"看到 error 就 FAIL"
  之类的逻辑。
- 另外有个 id_order.txt 文件,每行一个 model_id,定义最终 xlsx 的行序。
  在 id_order 里但根目录下找不到 => MISSING 行。
  在根目录下但不在 id_order 里 => 排到最后,notes 里加备注。

== 每个脚本的产出格式 ==
- 一轮一个文件。代码用一个 ```python``` 代码块包起来。
- 代码后面加一节 "## 快速测试",给出一段 bash 命令演示怎么跑,
  并用 3-5 行说明 fixture 是怎么搭的。不要真的执行,只是给说明。
- 不要写"以下是脚本……"之类的 preamble,直接出代码。

收到请回复"准备好了",然后等我发 Part 1。

Part 1 / 3:写 `scripts/parse_conversion.py`。

== 用途 ==
遍历回归测试根目录,找到每个模型最新的 conversion 日志,判定 PASS / FAIL /
NO_LOG,把结果写成一份 JSON。

== CLI 参数 ==
  --root PATH    必填,根目录(下面是各模型子目录)
  --out  PATH    必填,JSON 输出路径
  --verbose/-v   每处理一个模型在 stderr 打一行

== 算法 ==
1. 列出 --root 下所有直接子目录,逐个处理:
   a. 用正则 `^(?P<id>\d+[-_]\d+)_(?P<name>.+)$` 匹配目录名:
      - 不匹配 => 标 SKIPPED,加进顶层的 `skipped_directories` 列表,
        【不要】放进 `results` 字典。
   b. 进入 `<模型目录>/Convertion_result/convert/.log/` 看里面的文件。
      该目录不存在 / 没有任何文件 => status = NO_LOG。
   c. 否则取 mtime 最新的文件(并列时按文件名倒序作为 tiebreak,保证确定性)。
   d. 读这份文件(utf-8、errors='replace'),把整份文本传给 classify_log
      函数(见下面"判定规则的代码组织"一节),拿到 (status, fail_reason,
      evidence) 三元组。
2. 单个模型抛异常 => status=ERROR,异常信息写进 notes,fail_reason 留空。

== 判定规则的代码组织(重要) ==

判定逻辑【目前】只看一条规则:日志里出现
`^Traceback \(most recent call last\):\s*$` 这一行 => FAIL。

但要注意:这套规则【以后大概率会扩充】 —— 比如 SDK 段错误、被 kill
掉、写出非法产物但进程 0 退出之类的失败,不会留下 Python traceback。
所以代码必须把"以后能加规则"的口子留好,而不是把 traceback 检查
直接写死在主流程里。

具体要求:

1. 写一个独立函数,签名:
     def classify_log(log_text: str) -> tuple[str, str, str]:
         """返回 (status, fail_reason, evidence)。
         status ∈ {"PASS", "FAIL"}。
         fail_reason: FAIL 时是命中的规则名(当前固定为 "traceback");
                      PASS 时是空串。
         evidence: FAIL 时是触发判定的证据文本(traceback 块原文);
                   PASS 时是空串。"""

2. 函数内部用一个【按顺序检查的规则列表】,每条规则一个小函数,
   函数签名是 `Callable[[str], Optional[str]]`:输入完整日志文本,
   返回命中证据(字符串)或 None。结构形如:

     RULES: list[tuple[str, Callable[[str], Optional[str]]]] = [
         ("traceback", _check_traceback),
         # 以后追加新规则就在这里 append 一个 tuple
     ]

3. classify_log 主体逻辑:遍历 RULES,任一规则返回非 None 就立刻
   FAIL,fail_reason 取该规则名,evidence 取返回的证据文本;
   全部规则都返回 None 就 PASS。

4. 在 RULES 定义【上方】加一段醒目的注释,标题就叫
   "FAILURE DETECTION RULES — extend here",写清楚:
   - 当前规则:traceback 出现
   - 怎么加新规则:写一个 _check_xxx(log_text) -> Optional[str]
     函数,在 RULES 列表里 append ("xxx", _check_xxx)
   - 警告:不要用裸的 "error" / "warning" / "fail" 字面词匹配,
     因为成功 case 也常打这些词。要加这类规则必须用更精确的
     锚点(比如行首大写 "^FATAL: " 这种)
   - 警告:_check_xxx 函数返回的证据文本会进 JSON 的 evidence 字段
     和最终 xlsx 的 traceback 列,所以应该是【人类可读、能用来排查
     问题】的那一段,不是简单的 "matched" 标记

5. _check_traceback 的实现就是后面"traceback 抓取规则"那一节描述的逻辑,
   找不到返回 None,找到就返回抓出来的 traceback 块文本。

不要写"插件加载机制""动态注册""配置文件读取"之类的过度设计。
就是一个 list,里面放 tuple,直白。

== traceback 抓取规则(_check_traceback 内部用) ==

一份日志里可能有多个 traceback。【只抓最后一段】,因为前面的
traceback 经常是被 re-raise 后又处理掉了的,真正致命的是最后一段。

抓取算法:
1. 找出所有匹配 `^Traceback \(most recent call last\):\s*$` 的行,
   一个都没有 => 返回 None。
2. 从最后一处的那一行开始,继续吃后续的行。被吃进来的条件是
   【任一满足】:
   - 行以空格或 tab 开头(缩进的栈帧行),或
   - 是缩进栈帧之后的第一个非缩进非空行(也就是异常摘要行,
     例如 `ValueError: foo`)
3. 停止条件【任一满足】:
   - 摘要行已经被吃了之后,遇到一个空行,或
   - 摘要行已经被吃了之后,遇到一个非缩进非空行,或
   - 累计已经吃满 200 行(上限,触发上限就追加一行
     `... [traceback truncated by parser at 200 lines]` 然后停)
4. 摘要行出现之前,可以容忍中间夹一个空行(不要因为一个空行就早停)。
5. 把吃进来的所有行用 \n 拼起来返回。

== 输出 JSON 结构 ==
{
  "root": "<绝对路径>",
  "summary": {"PASS": N, "FAIL": N, "NO_LOG": N, "SKIPPED": N, "ERROR": N},
  "skipped_directories": ["...", ...],
  "results": {
    "<目录名>": {
      "dir_name": "...",
      "model_id": "01-01",
      "model_name": "YOLO_v4_1",
      "status": "PASS" | "FAIL" | "NO_LOG" | "ERROR",
      "fail_reason": "<规则名,例如 'traceback';非 FAIL 时为空串>",
      "log_path": "<绝对路径或 null>",
      "traceback": "<evidence 文本,FAIL 时是抓到的证据块,
                     非 FAIL 时为空串>",
      "notes": "<空串或人类可读说明>"
    }, ...
  }
}

注意:traceback 这个字段名虽然叫 traceback,但其实存的是 evidence
(因为目前只有 traceback 一种证据,所以字段名沿用)。后面如果加了
新规则,evidence 可能是别的内容,比如段错误信息;字段名暂不改,
保持向后兼容。

== 必须处理的边界情况 ==
- 日志文件读不开(权限/解码失败):catch 住,status=ERROR,原因进 notes。
- .log 目录存在但是空的:NO_LOG。
- 一份日志里有多个 traceback:只抓【最后一段】。
- .log 目录下文件名很奇怪(比如不以 .log 结尾):仍然纳入,mtime 说了算。


Part 2 / 3:写 `scripts/parse_snr.py`。

== 用途 ==
遍历同一个根目录,从每个模型的 SNR 日志里抽取 SNR 指标。
SNR 日志的具体格式有可能后面要调整,所以本脚本要把所有"格式相关"的
正则常量集中放在脚本顶部一个【显眼的 ADAPT 块】里,方便用户改。

== CLI 参数 ==
  --root PATH    必填
  --out  PATH    必填
  --verbose/-v

== ADAPT 块(放在脚本顶部,用一圈醒目的横线注释包起来) ==
- SNR_LOG_DIRS_RELATIVE:候选相对路径列表,按优先级排序。
  默认值:
    [Convertion_result/snr/.log,
     Convertion_result/snr,
     snr]
- SNR_LOG_GLOB:文件名 glob,默认 "*.log"
- SNR_KEY_PATTERNS:dict,key 是输出字段名,value 是已编译的正则,
  正则里【正好】有一个捕获组。匹配时不区分大小写。默认值:
    model_id    : ^\s*model[_\s]*id\s*[:=]\s*(.+?)\s*$
    model_name  : ^\s*model[_\s]*name\s*[:=]\s*(.+?)\s*$
    sdk_version : ^\s*sdk[_\s]*version\s*[:=]\s*(.+?)\s*$
    snr         : ^\s*snr\s*[:=]\s*([-+0-9.eE]+)\s*(?:dB)?\s*$
    dtype_org   : ^\s*dtype[_\s]*org\s*[:=]\s*(.+?)\s*$
    dtype_hw    : ^\s*dtype[_\s]*hw\s*[:=]\s*(.+?)\s*$
- REQUIRED_KEYS:一个 block 必须包含的字段集合。默认 {"snr"}。

== 算法 ==
1. 对每个目录名匹配 Part 1 同款正则的子目录:
   a. 按 SNR_LOG_DIRS_RELATIVE 顺序去找,把所有匹配 SNR_LOG_GLOB 的
      文件收集起来,按 mtime 倒序排。
   b. 【只用最新的那一份】,不要跨文件合并(跨文件合并会让结果不可
      预测)。
   c. 把文件解析成若干 block。block 是一组连续的 key:value 行。
      block 的边界是【任一满足】:
        - 一行空行,或
        - 某个 key 重复出现(典型是 `model_id` 又出现一次)
      不匹配任何 key 的行视为噪声,直接忽略。
   d. 一个 block 必须包含 REQUIRED_KEYS 里的所有 key 才算有效记录;
      不满足就【静默丢弃】。
2. 一个模型目录可能产出 0、1 或多条记录(比如不同 dtype 配置各一条),
   全部输出,后面 xlsx 步骤负责折叠。

== 输出 JSON 结构 ==
{
  "root": "<绝对路径>",
  "summary": {
    "models_with_snr_log": N,
    "models_without_snr_log": N,
    "total_records": N
  },
  "by_dir": {
    "<目录名>": {
      "dir_name": "...",
      "model_id_dir": "01-01",         # 来自目录名正则
      "model_name_dir": "YOLO_v4_1",   # 来自目录名正则
      "records": [
        {"model_id": "...", "model_name": "...", "sdk_version": "...",
         "snr": "...", "dtype_org": "...", "dtype_hw": "..."},
        ...
      ],
      "source_files": ["<绝对路径>"],
      "notes": "<空串 | 'no SNR log found' | 'no parseable SNR records'>"
    }, ...
  }
}

== 备注 ==
- 文件读不开不要崩,records 留空 + notes 写明原因即可。
- 目录名不匹配模型正则的:跳过,不出现在 by_dir 里。





Part 3 / 3:写 `scripts/build_xlsx.py`。

== 用途 ==
把 Part 1、Part 2 的两份 JSON 合并成一份 xlsx 报告,行序按 id_order.txt。

== CLI 参数 ==
  --conversion PATH  必填,Part 1 输出的 conversion.json
  --snr        PATH  必填,Part 2 输出的 snr.json
  --order      PATH  可选,id_order.txt;不传就按目录名字母序兜底,
                     并在 stderr 打 warning
  --out        PATH  必填,xlsx 输出路径

== 依赖 ==
- openpyxl。import 失败时打印
  `ERROR: openpyxl is required. Install with: pip install openpyxl`,
  退出码 2。

== id_order.txt 格式 ==
- 每行一个 model_id。
- # 开头的行是注释,空行忽略。

== xlsx 列顺序(表头加粗、首行冻结) ==
  model_id            (列宽 12)
  model_name          (列宽 28)
  conversion_status   (列宽 14)
  sdk_version         (列宽 14)
  snr                 (列宽 16)
  dtype_org           (列宽 12)
  dtype_hw            (列宽 12)
  conversion_log_path (列宽 60)
  traceback           (列宽 80)
  notes               (列宽 36)

== 行模型 ==
- 一个目录一行(目录名唯一,这是用户确认过的)。
- 一个模型有多条 SNR 记录的话,【在同一行内用换行符 \n 拼起来】,
  例如:snr 单元格 = "42.7\n38.1",dtype_hw 单元格 = "int8\nint4"。
  同一行,多行单元格。所有数据单元格都开 wrap_text=True。
- 状态填色:
    PASS    => 浅绿 #C8E6C9
    FAIL    => 浅红 #FFCDD2
    NO_LOG  => 浅黄 #FFF9C4
    MISSING => 浅灰 #ECEFF1
    ERROR   => 橙色 #FFAB91

== 排序算法 ==
1. 把 id_order.txt 读成列表 `order`(没传就 None)。
2. 把 conversion.json 里的 results 按 model_id 建索引(异常情况下
   一个 model_id 可能对应多个目录,全部输出,在 stderr 给个 warning)。
3. 如果 order 给了:
   - 按 order 顺序逐个 model_id 处理:
     * 找到对应目录 => 每个匹配的目录输出一行,标记为已用。
     * 没找到 => 输出一条 MISSING 行,model_id 填上,model_name 留空,
       notes = "model_id in id_order but no matching dir"。
   - 处理完 order 之后,把"在 conversion 数据里但没在 order 里"的目录
     按字母序追加,notes 后面补一句 ", not in id_order.txt"。
4. 如果 order 没给:目录名字母序排,stderr 打 warning。

== notes 列合并 ==
- notes 同时合并 conversion 那边的 notes 和 snr 那边的 notes,
  比如 "no log file under ..." + "no SNR log found",用 "; " 连接。
- 不要重复 status 已经表达过的信息。

== 一些细节 ==
- A2 处冻结窗格。














请帮我写一份 SKILL.md,用于一个名为 qa-regression-parser 的 skill。
这个 skill 的作用是把模型量化回归测试的结果(conversion 日志 + SNR 日志)
解析后输出成一份 xlsx 报告。skill 由三个独立 CLI 脚本组成,分别是
parse_conversion.py、parse_snr.py、build_xlsx.py,统一放在 scripts/ 下。

== 输出要求 ==
- 一个完整的 SKILL.md 文件,Markdown 格式,顶部有 YAML frontmatter。
- 直接出文件内容,不要写"以下是文件……"之类的 preamble。
- 用 ```markdown``` 代码块包起来。
- 用中文写正文,但是 frontmatter 里的 name 和命令行示例保持英文。

== YAML frontmatter ==
只有两个字段:
  name: qa-regression-parser
  description: <一段话,见下>

description 字段非常重要,它是这个 skill 被触发的【唯一依据】 —— 当用户
说类似的话时,coding agent 会去读取这份 SKILL.md。所以 description 要:
- 第一句先说 skill 干什么(parse 模型量化回归测试结果,产 xlsx 报告)
- 第二句开始列触发场景,要"主动"一些。常见的触发说法举例:
  "解析 conversion 日志"、"看一下哪些模型跑挂了"、"出回归报告"、
  "汇总 SNR"、"批量处理 Convertion_result"、用户直接给一个根目录
  问"这次跑得怎么样"、提到 id_order.txt 文件等等。把这些场景都
  涵盖进去,即使用户没说"用 qa-regression-parser"也要能触发。
- 整段控制在 3-5 句话,不要太长。
- 用英文写(描述触发场景,英文 agent 匹配更准),但中间可以混中文
  关键词比如 "Convertion_result"。

== 正文结构(Markdown 一级标题用 #,二级用 ##) ==

# QA Regression Parser

(一段话总述,讲清楚这个 skill 把什么变成什么)

## 何时使用本 skill

(列出触发信号。包括目录结构特征 —— 子目录名形如 01-01_YOLO_v4_1、
存在 Convertion_result/ 这种特征目录、用户提到 id_order.txt、
用户问"哪些模型挂了"等。明确说"用户不需要用确切的关键词",
看到这些信号就该用。)

## 输入目录的假设布局

(用一段代码块画出预期的目录树。包括:根目录下若干 <id>_<name>/
子目录,每个子目录下有一个同名的模型文件(扩展名不固定,我们也不读它)、
有 Convertion_result/convert/.log/*.log 多份(只看 mtime 最新一份)、
SNR 日志通常在 Convertion_result/snr/ 或 Convertion_result/snr/.log/。
另外还有一个根目录外的 id_order.txt,每行一个 model_id。)

## conversion 判定规则

(明确强调【纯规则】,不要再做花式判断:
  - FAIL: 最新 log 里出现 `Traceback (most recent call last):` 这一行
  - PASS: 没出现
  - NO_LOG: 模型目录在但 .log 目录下没文件
  - MISSING: id_order.txt 里有但根目录下没这个模型
  - SKIPPED: 目录名不符合 <id>_<name> 正则,会被记到单独 list,不进结果
日志里的 "warning" "error" "fail" 字面词【一律不算 FAIL】,因为这套
跑测里成功的 case 也经常打这些词。只有 traceback 标记算。)

## 怎么用

(分三步给出 bash 命令示例,每步一段。重点说明:三步是独立的、可以
分别重跑、中间有 JSON 文件可以 diff。如果用户没提供 id_order.txt,
build_xlsx.py 会按字母序兜底并打 warning。)

## 输出 xlsx 的列结构

(列一个 Markdown 表格,列出列名 / 来自哪个脚本 / 备注。列顺序就是:
model_id, model_name, conversion_status, sdk_version, snr, dtype_org,
dtype_hw, conversion_log_path, traceback, notes。最后说一句:FAIL 行
有红色高亮、PASS 绿色、NO_LOG 黄色、MISSING 灰色;traceback 列
开了自动换行,可以直接看完整内容。)

## 一个模型多条 SNR 记录怎么办

(用户已确认目录名 <model_id>_<model_name> 是唯一的,所以一个目录
保证一行。如果该目录的 SNR 日志里有多条记录,比如不同 dtype 配置
各一条,xlsx 里在【同一行】用 \n 把多条记录拼起来,
例如 snr 单元格 = "42.7\n38.1"、dtype_hw 单元格 = "int8\nint4"。
不要拆成多行。)

## 稳定性设计取舍

(用 bullet list 列出来,每条一行解释为什么这么做:
  - 最新 log 用 mtime 取,不用文件名排序(命名不规则)
  - 目录名走严格正则,不匹配就跳过,不让脚本崩
  - 单模型异常被 catch,落到 notes 列,继续处理其他模型
  - utf-8 + errors=replace,容忍乱码
  - traceback 抓取 200 行上限,防日志爆炸
  - 中间 JSON pretty-print,可以 diff
  - 多 traceback 抓最后一段(前面的常被 re-raise 后处理掉了))

## 适配你自己的 SNR 日志格式

(说明 parse_snr.py 顶部有一个显眼的 ADAPT 注释块,里面是
SNR_LOG_DIRS_RELATIVE / SNR_KEY_PATTERNS / REQUIRED_KEYS 三个常量。
拿到一份真实 SNR 日志后:1) 看一眼格式,2) 改这三个常量,3) 重跑。
不要去动主体逻辑。)

## 本 skill 不做的事

(诚实列出范围外的:
  - 不解读 SNR 数值好坏(没有阈值判断,只如实转录)
  - 不做 LLM 报错根因分析。traceback 已原样进 xlsx,需要根因总结时
    把 FAIL 行的 traceback 列复制出来单独问 agent 即可。
  - 不修改输入目录任何文件。)

== 写作风格 ==
- 用陈述句、祈使句,不要"我们建议"、"也许可以"这种弱措辞。
- 解释【为什么】这么做,而不是只说【怎么做】。比如说"用 mtime 取最新"
  之后要补一句"因为文件名命名不规则,字母序不可靠"。
- 不要长篇大论。每节控制在合理长度,整份 SKILL.md 不要超过 200 行。
- 不要用 emoji。







- 表头字体加粗。
- 所有数据单元格:vertical=top、wrap_text=True。
- 不要尝试自适应列宽(openpyxl 在无 GUI 环境下不可靠),用上面写死的列宽。

== 退出码 ==
- 即使有 warning 也是 0。
- 只在 argparse 报错或 openpyxl 缺失时返回 2。





