# 架构

## 三层

```
        宿主 Agent（LLM）
              │  提情景、判机制
              ▼
   ┌─────────────────────┐
   │  Controller         │  轮数上限、去重、快照、回滚、审批
   └─────────────────────┘
      │      │      │
      ▼      ▼      ▼
  Explorer  Critic  Rule Architect
      │      │      │
      └──────┴──────┘
              ▼
        World Model（纯数据）
```

## 为什么 LLM 不在核心层

**因为要能测。**

**「这条交互有没有规则覆盖」是布尔判断，不该由模型随机回答。**
**「这条机制是不是更通用」才是模型该干的。**

**所以：**

| 谁做 | 做什么 |
|---|---|
| **Python** | 状态、匹配、冲突、上限、快照、回滚 |
| **宿主 Agent** | 提情景、写机制、判通用性 |
| **作者** | approve / reject |

## 数据流

1. `load_world()` 读 `world.json`，`validate()` 查引用完整性
2. `generate_probes()` 按「同地点实体两两组合」造情景
3. `critic.analyse()` 查有没有规则覆盖 → 没覆盖就是缺口
4. `rules.propose()` 把缺口转成提案（含冲突检查）
5. `Controller.approve()` 才写进 `world.rules`
6. `counterfactuals()` 用新规则的作用域造下一轮情景
7. 撞到上限、或一轮没有新缺口，就停

## 停止条件

- `rounds` 到顶
- `max_scenarios` 到顶
- 一轮没有新缺口（`no_new_findings`）
- 提案数到顶（`max_proposals`）

**四条任一满足就停。不会无限递归。**
