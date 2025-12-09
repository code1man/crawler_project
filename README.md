# 舆情分析系统

一个集成爬虫、AI分析和数据可视化的舆情分析工具。支持小红书、知乎平台的评论爬取，并通过Coze AI进行情感分析和关键词提取，最终使用ECharts生成词云和情感分布图表。

## 📦 环境要求

### Python版本
- Python 3.8+

### Conda环境
```bash
# 激活环境
conda activate fgo_downloader
```

### 依赖包安装
```bash
pip install -r requirements.txt
```

#### requirements.txt 内容：
| 包名         | 说明                       |
| ------------ | -------------------------- |
| Flask        | Web框架                    |
| DrissionPage | 浏览器自动化（小红书爬虫） |
| requests     | HTTP请求（知乎API）        |
| tqdm         | 进度条                     |
| cozepy       | Coze AI SDK                |
| pandas       | 数据处理                   |
| openpyxl     | Excel支持                  |
| chardet      | 编码检测（可选）           |

---

## 🚀 启动方式

```bash
conda activate fgo_downloader
cd d:\pythonTools\crawler_project
python app.py
```

启动后访问：http://127.0.0.1:5000

---

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

### 配置说明
在 `utils/ai_agent.py` 中配置：
```python
COZE_API_TOKEN = "pat_xxxxx"  # Coze平台个人令牌
WORKFLOW_ID = "7581414272291733544"  # 工作流ID
```

### 获取Token
1. 登录 https://www.coze.cn
2. 进入"API令牌"页面
3. 创建新令牌并复制

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

## 📁 项目结构

```
crawler_project/
├── app.py                 # Flask主应用
├── requirements.txt       # 依赖包
├── README.md             # 本文档
├── spiders/
│   ├── __init__.py
│   ├── xhs_spider.py     # 小红书爬虫
│   └── zhihu_spider.py   # 知乎爬虫
├── utils/
│   ├── __init__.py
│   ├── ai_agent.py       # Coze AI接口
│   └── cleaner.py        # 数据清洗
├── templates/
│   └── index.html        # 前端页面
└── resource/
    └── result/           # 结果存放目录
```

---

## 🔧 常见问题

### 1. ModuleNotFoundError: No module named 'cozepy'
```bash
conda activate fgo_downloader
pip install cozepy -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2. 知乎爬取返回0条结果
- 检查Cookie是否有效（浏览器F12 → Network → 复制Cookie）
- 确保已禁用系统代理

### 3. CSV编码错误
- 系统已支持自动编码检测
- 如仍有问题，尝试用记事本另存为UTF-8格式

### 4. Coze API Token过期
- 重新登录Coze平台获取新Token
- 更新 `utils/ai_agent.py` 中的 `COZE_API_TOKEN`

### 5. 词云图表不显示
- 确保浏览器能访问unpkg.com CDN
- 检查Console是否有JavaScript错误

---

## 📝 更新日志

- 支持多CSV合并和统一分析
- 添加ECharts词云和情感分布图
- 知乎15种搜索策略突破200条限制
- AI批量分析改为50条/批CSV格式
- 自动编码检测支持多种中文编码
