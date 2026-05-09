# Knowledge Builder Skill

帮助用户自动构建、组织和管理 LLM 友好的知识库（Wiki），遵循 Karpathy 的 LLM Wiki 原则。

## 目录结构

```
knowledge_builder/
  knowledge_builder.md    ← 主 skill 文件（Agent 加载）
  templates/
    INDEX_template.md     ← 知识库总索引模板
    glossary_template.md  ← 术语表模板
    page_template.md      ← 知识页面模板
  README.md               ← 使用说明
```

## 功能

1. **创建知识库** — 按主题在 `data/kg_graph/<topic>/` 下创建结构化知识库
2. **导入内容** — 将文件、文本内容转换为 Wiki 格式并导入
3. **更新知识库** — 增量更新已有页面，维护版本状态
4. **查询知识库** — 按关键词/标签搜索相关内容
5. **维护健康** — 检查 broken links、重复内容、过期页面

## 使用场景

- "帮我建一个关于 Python 的知识库"
- "把这份笔记整理到知识库中"
- "知识库中关于 XX 的内容有哪些？"
- "更新 XX 页面的内容"
- "检查一下知识库有没有重复或死链"

## 知识库存储位置

`data/kg_graph/<topic-name>/`

其中 `topic-name` 为英文小写 + 连字符，如：
- `machine-learning`
- `web-development`
- `finance-notes`
