# World Schema

```json
{
  "name": "world name",
  "canon": ["已确立的设定，一句一条"],
  "constraints": ["世界不许违反的事"],
  "entities": {
    "<id>": {"id": "...", "name": "...", "tags": ["..."], "properties": {}, "location": "<loc id>"}
  },
  "locations": {
    "<id>": {"id": "...", "name": "...", "tags": ["..."], "properties": {}}
  },
  "rules": {
    "<id>": {
      "id": "...",
      "scope": ["tag", "tag"],
      "verb": "touch",
      "effect": {"harm": "lethal"},
      "rationale": "为什么要这条",
      "status": "CANON",
      "depends_on": ["<rule id>"],
      "source": "canon"
    }
  },
  "metadata": {}
}
```

## 规则匹配

**一条规则 `applies()` 成立，当且仅当：**

1. `verb` 相等
2. `scope` 里每个标签，都出现在（主体标签 ∪ 客体标签）里

**所以 `scope` 是**必须全部满足**的标签集合，不是任意一个。**

## status

| 值 | 含义 |
|---|---|
| `CANON` | 作者确认过 |
| `PROPOSED` | 提案，未入正史 |

**`apply()` 会把 `PROPOSED` 改成 `CANON`，并记下 `source = 提案 id`。**

## effect

**自由字段。工具不解释它，只比较相等与否（查冲突时）。**

**常见写法：** `{"harm": "lethal"}`、`{"moves": true}`、`{"impossible": true}`（后者用来标记规则冲突）。
