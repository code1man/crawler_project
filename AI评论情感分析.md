# 舆情分析系统

一个集成爬虫、AI分析和数据可视化的舆情分析工具。支持小红书、知乎平台的评论爬取，并通过Coze AI进行情感分析和关键词提取，最终使用ECharts生成词云和情感分布图表。

## 🕷️ 爬虫功能

### 支持平台

| 平台   | 方法                      | 说明                       |
| ------ | ------------------------- | -------------------------- |
| 小红书 | DrissionPage 浏览器自动化 | 模拟真实用户操作，支持翻页 |
| 知乎   | requests API调用          | 15种搜索策略突破200条限制  |

### 小红书爬虫 (`spiders/xhs_spider.py`)
- 使用 DrissionPage 模拟浏览器
- 自动滚动加载更多内容
- 支持多关键词搜索（逗号分隔）
- 自动去重

### 知乎爬虫 (`spiders/zhihu_spider.py`)
- 使用 requests 调用知乎搜索API
- **15种搜索策略**：综合/内容/回答/文章 × 默认/相关/点赞/时间
- 速度控制：每页2-4秒，策略间3-6秒
- 禁用系统代理避免SSL错误
- 需要Cookie登录（从浏览器F12获取）

### 使用方法
1. 在首页输入关键词（多个用逗号分隔）
2. 选择平台（小红书/知乎）
3. 设置爬取数量
4. 点击"开始爬取"
5. 爬取完成后可下载CSV

### 数据格式
爬取结果CSV格式：
```
keyword, url, user, comment_content
```

---

## 🤖 AI分析功能

### Coze AI集成 (`utils/ai_agent.py`)

使用扣子(Coze)平台的工作流进行智能分析：

| 功能       | 说明                   |
| ---------- | ---------------------- |
| 情感分析   | 判断评论正面/负面/中性 |
| 关键词提取 | 从评论中提取核心关键词 |
| 批量处理   | 每批50条，CSV格式发送  |

### 使用方法
1. 爬取或上传CSV数据
2. 设置分析数量（0=全部）
3. 点击"AI批量分析"
4. 等待SSE流式返回结果
5. 分析结果会追加到表格

### 返回格式
AI返回的分析结果包含：
- `keywords`: 提取的关键词（逗号分隔）
- `sentiment`: 情感倾向（positive/negative/neutral）
- `is_valid`: 是否有效评论

---

## 📊 ECharts可视化

### 图表类型

| 图表   | 库                | 说明             |
| ------ | ----------------- | ---------------- |
| 词云图 | echarts-wordcloud | 关键词频率可视化 |
| 饼图   | echarts           | 情感分布占比     |

### 前端依赖（CDN引入）
```html
<!-- ECharts核心 -->
<script src="https://unpkg.com/echarts@5/dist/echarts.min.js"></script>
<!-- 词云扩展 -->
<script src="https://unpkg.com/echarts-wordcloud@2/dist/echarts-wordcloud.min.js"></script>
```

### 数据来源
1. **TXT分析**：上传Coze返回的TXT结果文件
2. **CSV分析**：上传已合并的CSV文件（含keywords/sentiment列）
3. **多CSV统一分析**：上传多个CSV统一生成图表

### 功能说明

#### 1. TXT文件分析
- 上传AI分析返回的TXT文件
- 解析keywords和sentiment字段
- 只统计 `is_valid=true` 的有效数据

#### 2. CSV+TXT合并下载
- 上传原始CSV + AI分析TXT
- 自动匹配合并
- 下载包含分析结果的完整CSV

#### 3. 多CSV合并下载
- 选择多个CSV文件
- 合并为一个CSV（添加source_file列标记来源）
- 支持自动编码检测（utf-8/gbk/gb2312/gb18030）

#### 4. 多CSV统一分析
- 选择多个已分析CSV
- 统一统计关键词频率
- 统一统计情感分布
- 生成综合词云和饼图

### 图表配置
词云图参数：
- 字体大小：14-60px
- 旋转角度：-45° ~ 45°
- 颜色：10种随机配色

---

## 实现大致思路

- 输入规范化：统一读取爬虫输出（CSV，字段至少包含 `keyword, url, user, comment_content`），并做编码检测与清洗（见 `utils/cleaner.py`）。
- 分片与批处理：按配置把评论切成页（`page_size`，默认 10），每页作为一次合并问询提交给 Coze 工作流；可将若干页（`batch_pages`）并发提交以提高吞吐。
- 双路调用：先使用文档上传 API 上传原始 CSV（返回 `document_id`），再用工作流执行 API 提交包含 `document_id` 与本页 10 条问询的执行请求。
- 异步/流式处理：支持 SSE 或轮询获取执行结果，边接收边写回 CSV/数据库（保留 `job_id`、`page_index`、`row_index` 以便断点续传）。
- 结果合并：把返回的 `keywords, sentiment, is_valid` 写回原始表（新增列），并触发可视化数据生成。

## 使用的外部 API（参考 / 协议）

- 知乎爬取API
- Workflow Execution API：提交工作流执行，payload 包含 `workflow_id`, `document_id`, `items[{row_index, prompt, metadata}, ...]`。返回 `job_id` 与初始状态。
- Document Upload API：上传 CSV/文本作为工作流上下文，返回 `document_id`（multipart/form-data 或 base64 JSON）。
- Execution Results / Status API：查询或拉取执行结果（当不使用流式时）。
- Streaming (SSE) Events：若 Coze 支持，订阅 `GET /v1/executions/{job_id}/events` 实时接收每条分析结果。

（注：上面为通用接口命名，实际以 Coze 官方文档为准；认证通常使用 `Authorization: Bearer <API_KEY>`）

## 推荐 RESTful 接口（项目内）

- POST `/api/ai/analyze`
	- 描述：启动一次分析任务（上传文件或引用已有文件路径）。
	- 请求体（JSON 或 multipart）：`source("upload"|"path"), file (multipart), file_path, page_size, batch_pages, workflow_id, callback_url`。
	- 返回：`{ job_id, status, pages }`。
- GET `/api/ai/status/{job_id}`
	- 描述：查询任务状态与进度。
	- 返回：`{ job_id, status, progress, errors }`。
- GET `/api/ai/result/{job_id}`
	- 描述：获取合并后的分析结果（JSON 或下载链接）。
	- 返回：`{ job_id, result_url, summary }`。
- POST `/api/ai/upload-doc`
	- 描述：单独上传文档，返回 `document_id` 供 workflow 使用。
- POST `/api/ai/retry/{job_id}`
	- 描述：对失败页或失败条目触发重试。
- POST `/api/ai/cancel/{job_id}`
	- 描述：取消正在进行的任务。

## Coze 工作流批处理与文档上传思路

1. 页面分片（Page）：把数据按 `page_size=10` 切分，每页生成 10 条子问询（每条问询用于一条评论的情感、关键词和有效性判定）。
2. 合并请求：将一页的 10 条问询合并为单个工作流执行请求，减少 HTTP 请求开销并便于对原始行索引的关联。
3. 文档作为上下文：若需要基于整表或历史上下文检索，先用 Document Upload API 上传 CSV，工作流中引用 `document_id`，避免把整表塞入 prompt。
4. 批次并发：将多个页（`batch_pages`）并发提交，受限于并发上限与 Coze 的速率限制（默认并发 4-8）。
5. 结果消费：优先使用 SSE 实时接收结果；若不可用，使用 `GET /v1/executions/{job_id}/results` 批量拉取。
6. 重试与幂等：记录每条 `row_index` 的状态（pending/processing/done/failed），失败放入重试队列，支持手动/自动重试。