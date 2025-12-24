好，这里我**严格只说明你负责的部分**，不碰 AI 内部实现，也不解释爬虫细节。
下面这份可以 **直接作为对接文档**，重点只有三件事：

* ✅ Watch（舆情订阅）做了什么
* ✅ 前后端 Watch API 怎么用
* ✅ 字段含义与数据流向

你可以保存为 **`WATCH_API.md`**。

---

# 舆情订阅（Watch）模块 API 说明

> 本文档仅描述 **Watch（舆情订阅 & 告警）模块**
> 包含前端 ↔ 后端接口定义、字段含义及执行流程
> **不涉及 AI 内部分析逻辑**

---

## 一、Watch 模块职责边界（你负责的部分）

### Watch 模块负责什么？

✔ 定义订阅规则
✔ 定期或手动触发一次“舆情检查”
✔ 统一调度：爬取 → AI → 统计 → 阈值判断
✔ 在满足条件时触发通知（邮件）

### Watch 模块 **不负责**

✘ AI 模型如何分析
✘ 情感标签如何生成
✘ AI 接口的鉴权与稳定性

---

## 二、Watch 执行整体流程（非常重要）

> 以下流程由 **后端 Watch 模块统一控制**

```
1. Watch 被触发（定时 / test 接口）
2. 根据 keyword + platform 执行爬虫
3. 将获取的数据送入 AI 分析模块
4. 汇总 AI 返回结果：
   - total
   - valid
   - positive
   - negative
5. 判断是否满足告警阈值
6. 若满足 → 发送邮件
7. 返回本次 Watch 执行结果
```

---

## 三、前端 ↔ 后端 API 列表（Watch 专用）

### 1️⃣ 获取订阅列表

#### GET `/api/watch`

**说明**
前端页面初始化 / 点击「刷新」时调用

**返回示例**

```json
{
  "code": 200,
  "data": [
    {
      "id": 1,
      "keyword": "AI问诊",
      "platform": "xhs",
      "interval_seconds": 3600,
      "negative_threshold": 1,
      "enabled": true,
      "notify": {
        "email": "xxx@qq.com"
      }
    }
  ]
}
```

#### 字段说明

| 字段                 | 含义                  |
| ------------------ | ------------------- |
| id                 | 订阅唯一 ID             |
| keyword            | 监控关键词               |
| platform           | 数据来源平台（xhs / zhihu） |
| interval_seconds   | 后端存储的执行周期（秒）        |
| negative_threshold | 负面告警阈值              |
| enabled            | 是否启用                |
| notify.email       | 告警邮箱                |

---

### 2️⃣ 创建订阅

#### POST `/api/watch`

**前端提交**

```json
{
  "keyword": "AI问诊",
  "platform": "xhs",
  "interval_minutes": 60,
  "negative_threshold": 1,
  "notify": {
    "email": "xxx@qq.com"
  },
  "enabled": true
}
```

#### 字段说明（前端 → 后端）

| 字段                 | 说明            |
| ------------------ | ------------- |
| keyword            | 关键词           |
| platform           | 平台            |
| interval_minutes   | 执行周期（分钟，前端输入） |
| negative_threshold | 负面数量阈值        |
| notify.email       | 告警邮箱          |
| enabled            | 是否立即启用        |

📌 **说明**

* 后端会将 `interval_minutes` 转换为 `interval_seconds` 存储
* Watch 创建后即可被定时器或 test 接口触发

---

### 3️⃣ 启用 / 停用订阅

#### POST `/api/watch/{id}/enable`

**请求**

```json
{
  "enabled": false
}
```

**说明**

* 不删除订阅
* 仅控制是否参与调度

---

### 4️⃣ 手动测试订阅（核心接口）

#### POST `/api/watch/{id}/test`

**用途**

* 手动执行一次完整 Watch 流程
* 用于：

  * 演示
  * 调试
  * 验证邮件是否能发

**执行内容**

```
爬虫 → AI 分析 → 统计 → 阈值判断 →（可选）邮件
```

---

### 5️⃣ 删除订阅

#### DELETE `/api/watch/{id}`

---

## 四、Watch 执行结果结构（后端返回）

> Watch 执行结束后，后端会生成一次结果对象

```python
{
  "ok": True,
  "triggered": False,
  "keyword": "AI问诊",
  "platform": "xhs",
  "total": 1,
  "valid": 0,
  "positive": 0,
  "negative": 0,
  "reasons": []
}
```

### 字段含义说明（非常重要）

| 字段        | 含义                        |
| --------- | ------------------------- |
| ok        | Watch 流程是否正常跑完（不等于 AI 成功） |
| triggered | 是否触发告警                    |
| keyword   | 本次监控关键词                   |
| platform  | 平台                        |
| total     | 本次爬取到的舆情条数                |
| valid     | AI 判定为有效的条数               |
| positive  | 正面条数                      |
| negative  | 负面条数                      |
| reasons   | 告警触发原因说明                  |

⚠️ **关键说明**

> `ok = True`
> 只表示 **流程跑完**，不代表 AI 返回了有效结果

当 AI 鉴权失败时：

* valid / negative 可能为 0
* Watch 不会触发告警
* 但流程仍会结束并返回结果

---

## 五、告警触发规则（你实现的逻辑）

```python
if negative >= negative_threshold:
    triggered = True
    send_email()
else:
    triggered = False
```

📌 **说明**

* Watch 模块只关心“统计结果”
* AI 如何得出 negative 数量，不在 Watch 负责范围内

---

## 六、前端 Watch 页面字段绑定关系

### 创建订阅表单（前端）

```js
watchForm = {
  keyword,
  platform,
  interval_minutes,
  negative_threshold,
  email
}
```

### 列表展示字段（来自 GET /api/watch）

```js
watchList = [
  {
    id,
    keyword,
    platform,
    interval_seconds,
    enabled
  }
]
```

---

## 七、结论（给对接人的一句话版本）

> Watch 模块是一个 **规则驱动的调度与告警系统**：
> 它不做 AI，只负责在合适的时间调用 AI、统计结果并按规则发通知。

---

如果你需要，我可以再帮你：

* ✅ **压缩成一页「我负责模块说明」**（课程 / 答辩用）
* ✅ **补一张 Watch 执行时序图（纯 Watch，不含 AI 细节）**
* ✅ **帮你检查后端字段命名是否统一（interval / notify）**

你说一句「要哪一个」，我直接给成品。
