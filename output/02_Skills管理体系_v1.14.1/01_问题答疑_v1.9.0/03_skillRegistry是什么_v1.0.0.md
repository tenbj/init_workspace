# skillRegistry 是什么？为什么要引入？

> 用户疑问：不理解 `skillRegistry` 的用途和引入理由。

---

## 一句话回答

`skillRegistry` 是为了解决**文件夹名带版本号后，每次 bump 版本都要到处改路径引用**这个问题而提出的。**如果你不打算给 Skill 文件夹加版本号，就不需要 skillRegistry。**

---

## 问题根源

当前 Skill 文件夹名不带版本号（如 `框架体检`），所以路径是稳定的：

```
.agents/skills/框架体检/scripts/framework-check.ps1
```

这个路径写死在 `workspace-spec.json`、`version-control-rules.md` 里，不会变。

**但是**，AB 方案提出给文件夹加版本号（如 `A01_框架体检_v1.2.0`），路径就变成了：

```
.agents/skills/A01_框架体检_v1.2.0/scripts/framework-check.ps1
```

每次 Skill 版本 bump（如 v1.2.0 → v1.3.0），文件夹名变了，**所有引用这个路径的地方都要跟着改**：

| 要改的地方 | 数量 |
|-----------|------|
| `workspace-spec.json` 的 `bomCheck.files` | 1 处 |
| `version-control-rules.md` 的脚本路径表 | 1 处 |
| `SKILL.md` 内的脚本调用示例 | 1-5 处 |
| 其他 SKILL.md 的交叉引用路径 | 0-2 处 |

**每改一次 Skill，就要人肉更新 3-8 处路径。** 这很容易遗漏。

---

## skillRegistry 怎么解决这个问题

在 `workspace-spec.json` 中增加一个"查找表"：

```json
{
  "skillRegistry": {
    "B01": { "folder": "B01_框架体检_v1.2.0" },
    "B02": { "folder": "B02_版本控制备份_v3.1.0" }
  }
}
```

然后其他地方都用稳定的编号 `B01` 来引用，脚本在运行时从 `skillRegistry` 查出当前的文件夹名：

```
bomCheck 说："去查 B01 的 scripts/framework-check.ps1"
→ 从 registry 查到 B01.folder = "B01_框架体检_v1.2.0"
→ 拼出完整路径 ".agents/skills/B01_框架体检_v1.2.0/scripts/framework-check.ps1"
```

Skill 版本 bump 后，**只需更新 `skillRegistry` 一处**，其他引用自动跟上。

---

## 结论：需不需要引入？

| 场景 | 需要 skillRegistry？ |
|------|-------------------|
| Skill 文件夹**不带版本号** | ❌ 不需要，路径本来就稳定 |
| Skill 文件夹**带版本号**，但 Skill 很少 bump | ⚠️ 可以不要，手动改路径能接受 |
| Skill 文件夹**带版本号**，且频繁 bump | ✅ 需要，否则每次改一堆路径 |

**当前建议**：先不引入。等 Skill 文件夹加上版本号后，实际跑几轮 bump，感受一下手动改路径的痛感。如果确实麻烦，再引入。
