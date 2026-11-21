# Recursive World Builder

**让 Agent 自己进入你的世界，撞出因果缺口，再把缺口补成通用规则。**

不是「再写一段设定」，是**对已有的世界做实验**。

```
世界模型 → 生成情景 → Agent 自演 → 观察后果 → 检出缺口
        → 提通用规则 → 反事实测试 → 一致性校验 → 补丁 → 再来一轮
```

---

## 核心主张

**缺口不是靠联想写出来的，是靠撞出来的。**

一个世界里有一条高压线，但没有任何规则说电对人做什么。
普通的生成器会补一句「触电会死」。
本工具会问：

- 这个世界有电流吗？
- 什么导电？
- 水导电吗？
- 绝缘鞋有用吗？
- 电和天气、物体破坏之间有交互吗？

**然后提一条能同时解释这些的机制，而不是五条特例。**

---

## 安装

```bash
git clone https://github.com/SakuraEntropia/recursive-world-builder.git
cd recursive-world-builder
pip install -e ".[dev]"
```

要求 Python 3.11+，只依赖标准库；测试用 pytest。

---

## 快速开始

```bash
# 跑内置演示世界
PYTHONPATH=src python -m recursive_world_builder.demo examples/electric_city

# 跑测试
pytest -q
```

输出：

```
rounds=2 scenarios=8 findings=3 proposals=3 stopped=no_new_findings
approving P-fc76af
rules now: ['R-805335', 'R-walk', 'R-wet']
counterfactual scenarios: 6
second pass findings: 4
```

**读法：** 第一轮撞出 3 个缺口，提 3 条提案；批准一条之后，规则集从 2 条变 3 条；
反事实又生成 6 个新情景，第二轮又撞出 4 个新缺口。

**这就是递归。**

---

## Skill 用法

本仓库同时是一个 Agent Skill（`skills/recursive-world-builder/SKILL.md`）。
装进宿主之后可以说：

```
/recursive-world-builder init ./my-world
/recursive-world-builder explore --rounds 5
/recursive-world-builder explore --focus physics
/recursive-world-builder proposals
/recursive-world-builder approve P-fc76af
```

**自然语言即可，不要求额外 CLI。**

---

## 五个模块

| 模块 | 文件 | 职责 |
|---|---|---|
| **World Model** | `model.py` | 实体、地点、规则、约束、正史 |
| **Explorer** | `explorer.py` | 生成情景与反事实 |
| **Causal Critic** | `critic.py` | 检出缺口，分三类 |
| **Rule Architect** | `rules.py` | 提通用规则，查冲突，批准后入正史 |
| **Controller** | `controller.py` | 轮数、去重、上限、回滚、审批 |

---

## 三种缺口，不能混

| 类型 | 含义 | 怎么处理 |
|---|---|---|
| **contradiction** | 有规则，但两条打架 | 报冲突，等作者裁 |
| **undefined_interaction** | 没有任何规则覆盖 | 提通用规则 |
| **counter_intuitive** | 有规则，但看着怪 | **不自动判错**——虚构世界允许违反常识 |

**第三条最要紧。**
**这个工具不许用现实常识去覆盖你的原创规则。**

---

## 规则是提案，不是正史

**任何新规则默认 `PROPOSED`。**

**没有 `approve` 就不会进 `CANON`。**

**`rollback()` 可以退回上一次快照。**

---

## 项目结构

```
src/recursive_world_builder/
  model.py      实体、地点、规则、世界
  storage.py    读写 world.json、读取 markdown 正史
  explorer.py   情景生成、反事实
  critic.py     缺口检出
  rules.py      提案、冲突检查、批准
  controller.py 循环、去重、上限、回滚
examples/electric_city/
tests/test_core.py
skills/recursive-world-builder/SKILL.md
docs/architecture.md
```

---

## 已知限制

**一、没有物理引擎。**
规则是声明式的，`effect` 是自由字段。工具不模拟流体、电路或经济。

**二、缺口检测是确定的，机制推导不是。**
Python 只负责：这条交互有没有规则覆盖、两条规则有没有冲突。
**哪条机制更好，由宿主 Agent 判断。**

**三、`confidence` 是主观判断。**
不是校准过的概率，别当统计量用。

**四、没有 LLM 也能跑。**
测试模式用预定义情景，验证闭环能转；真实推理要宿主 Agent。

**五、规则语言很窄。**
现在只支持 `(主体标签, 动词, 客体标签) → effect`。
不支持量词、时间、因果链。

---

## MIT

见 `LICENSE`。
