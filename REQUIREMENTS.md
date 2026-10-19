# PaperMind — Evidence-Grounded Research Intelligence Agent

## 完整工程开发任务书 | Production-Oriented Full-Stack AI Project

# 0. 最高优先级指令

你现在担任 PaperMind 项目的首席软件架构师、RAG 算法工程师、Agent 开发工程师、Python 后端工程师、全栈工程师、测试工程师和 DevOps 工程师。

你的任务不是讨论如何开发，而是**在当前代码仓库中，实际完成一个具备真实使用价值、可部署、可评测、可开源、能够作为高质量 AI Agent / RAG 开发实习简历项目的完整软件系统。**

项目名称：

**PaperMind — An Evidence-Grounded Research Agent for Scientific Experiment Analysis**

中文名称：

**PaperMind：基于实验感知 RAG 与可验证证据链的科研智能分析平台**

项目核心定位：

面向机器学习、深度学习、模型压缩及人工智能领域的研究人员，提供论文检索、结构化实验提取、跨论文实验公平比较、证据验证、Agentic Research 和科研知识库管理能力。

**项目不是通用 PDF Chatbot，不是简单的 LangChain Demo，也不是仅能自动生成论文摘要的工具。**

最终应成为一个能够由真实用户使用的科研分析平台。

## 0.1 工作方式

严格遵守以下规则：

1. 必须实际创建文件、编写代码、安装依赖、运行测试、修复错误，不允许只给出方案。
2. 采用增量式开发。先实现可以端到端运行的最小版本，再逐步增强。
3. 每完成一个开发阶段，都必须执行相应的测试并记录结果。
4. 在能够自主作出合理技术选择时，不需要反复向用户确认。
5. 不能使用假数据、Mock API 或硬编码回答伪装真实功能。Mock 仅用于明确隔离的测试环境。
6. 如果当前环境缺少 API Key、网络、GPU 或 Docker，先完成不依赖这些资源的真实代码，并明确记录未验证部分。
7. 不得声称未执行的测试已经通过。
8. 不得声称实现了学术创新，除非有充分的对比实验依据。
9. 所有技术组件使用真实存在、维护状态合理的版本，并核实官方文档。
10. 不要盲目照搬完整开源项目。可以使用成熟组件，但核心业务逻辑需要自主实现。
11. 所有模块必须具有清晰的接口、数据结构、错误处理和测试。
12. 必须考虑安全性、性能、可维护性和公开部署。
13. 所有进度记录在 `PROGRESS.md`，所有关键架构决策记录在 `docs/decisions/`。
14. 上下文空间不足时，必须先保存进度和下一步任务，保证新的 Coding Agent 会话可以继续开发。
15. 对依赖用户授权、外部付费资源、生产数据删除或其他不可逆操作的任务，必须遵守执行环境的权限和审批要求。

你的成功标准是：

**一个真实可运行的产品 + 三个有技术深度的核心创新模块 + 一套可复现的实验结果 + 完整部署能力。**

---

# 1. 项目背景与竞品分析

开发之前需要理解这个项目为什么存在。

现有开源项目包括：

- PaperQA2：https://github.com/Future-House/paper-qa
- Ai2 ScholarQA：https://github.com/allenai/ai2-scholarqa-lib
- OpenScholar：https://github.com/AkariAsai/OpenScholar
- STORM：https://github.com/stanford-oval/storm
- GPT Researcher：https://github.com/assafelovic/gpt-researcher
- Docling：https://github.com/docling-project/docling

这些系统已在不同程度上实现：

- 论文检索
- PDF 问答
- Agentic RAG
- 多轮检索
- 证据收集
- 引用生成
- 论文比较
- 自动文献综述

因此，PaperMind 不能将这些常规功能当作独有创新。

本项目应形成三个明确的技术差异化模块。

## 差异化模块 A：Experiment-Aware RAG

实验感知检索。

普通 RAG 只检索文本 Chunk。

PaperMind 需要同时理解与检索：

1. Paper：论文实体
2. Section：论文章节
3. Evidence：原文、表格、公式、图表说明
4. Experiment：结构化实验记录
5. Configuration：模型、数据集、精度、指标和实验条件

目标是使系统能够回答：

“哪些量化方法在相同模型、相同平均精度和相同数据集下进行过比较？”

而不是简单返回包含关键词的段落。

## 差异化模块 B：Experiment Comparability Engine

跨论文实验可比性判断引擎。

对两篇论文中的实验结果进行结构化条件校验。

判断：

- 是否使用相同模型及模型版本
- 是否使用相同数据集与数据划分
- 是否使用相同评价指标及计算协议
- 是否采用相同量化预算
- 是否具有相同量化对象和精度定义
- 校准设置是否一致
- 其他重要条件是否发生变化
- 是否存在影响结果解释的缺失信息

输出可解释的比较结论。

不能仅根据 Accuracy 数值大小判断方法优劣。

## 差异化模块 C：Claim–Evidence Verification

声明与证据校验。

系统回答中的关键声明必须能够追溯到原始论文证据。

例如：

“方法 A 在 PIQA 上达到 79.2% Accuracy。”

必须能够验证：

- 方法 A 对应哪一条实验记录
- 79.2% 是否是原始表格中的实际数值
- PIQA 是否对应表格的正确列
- Accuracy 是否为正确的指标
- 对应模型及实验条件是否一致
- 证据来自哪篇论文、哪一页、哪个表格或段落

**核心设计原则：LLM 负责理解与提取，结构化数据系统负责保存，确定性代码负责可验证规则，Agent 负责组织任务。**

以上是项目预期的差异化方向，不代表学术界首次提出。最终必须通过实验验证其价值。

---

# 2. 产品形态与真实使用场景

PaperMind 需要具备现代化 Web 应用界面。

用户打开网站后，可以创建科研知识库、上传论文、搜索论文、开展跨论文研究，并获得可核验的分析结果。

## 场景一：建立研究论文库

用户创建一个名为：

“LLM & MoE Quantization Research”

的知识库。

上传若干篇 PDF 论文后，系统自动执行：

1. 文件校验
2. PDF 解析
3. 标题与摘要提取
4. 章节识别
5. 表格结构提取
6. Chunking
7. Embedding
8. 向量索引构建
9. 实验章节识别
10. 实验记录结构化提取
11. 证据映射
12. 数据库存储

用户可以查看每篇论文的处理状态、提取记录和解析失败信息。

## 场景二：精准科研问答

用户提问：

“这篇论文使用了什么量化策略？”

系统通过 Hybrid RAG 找到相关方法章节，返回解释和可点击引用。

用户继续提问：

“它的实验结果主要来自哪张表？”

系统应当能够定位到具体表格及其对应结果。

## 场景三：跨论文实验比较

用户提问：

“比较论文库中 MoE 混合精度量化方法在 Qwen3-30B-A3B 上的 PIQA 准确率。”

系统应：

1. 识别需要进行结构化实验比较。
2. 确定目标模型、数据集、指标和其他约束。
3. 检索相关论文与实验记录。
4. 提取并规范化实验配置。
5. 进行可比性校验。
6. 生成结果对照表。
7. 标记不一致或未知条件。
8. 提供每个关键数值的原始证据。
9. 给出审慎的比较分析。

如果精度预算不同，应提醒用户这些结果不属于严格等预算比较。

## 场景四：自动实验结果提取

用户上传论文后，进入“Experiment Explorer”。

系统可以展示：

- 论文
- 方法
- 模型
- 量化精度
- 数据集
- 评价指标
- 实验结果
- 校准条件
- 实验备注
- 原始证据位置

用户可以手动检查和修正提取结果。

所有修改应保留必要的审计信息。

## 场景五：研究问题分析

用户提问：

“近几年 MoE 量化方法主要如何分配专家精度？不同策略有什么优缺点？”

Research Agent 自动规划任务、检索论文、收集证据、整理分类，并生成研究报告。

所有关键结论必须有可核验的论文来源。

## 场景六：多人在线使用

支持多个用户拥有各自的知识库。

用户 A 的私人论文和实验数据，不能被用户 B 的检索、Agent 工具调用或直接 API 访问获取。

---

# 3. 技术栈

采用 Python 优先、模块化、可独立部署的架构。

## 3.1 后端

必须使用：

- Python 3.11+
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- PostgreSQL
- Redis
- Celery 或功能等价的可靠任务框架
- pytest
- httpx
- Ruff

要求支持异步 API、依赖注入、统一错误处理、数据库迁移、结构化日志和自动化测试。

## 3.2 AI 与 RAG

必须使用：

- LangChain
- LangGraph
- Qdrant
- Docling
- Dense Embedding
- BM25 / Sparse Retrieval
- Reciprocal Rank Fusion
- Cross-Encoder Reranker
- Langfuse
- Ragas 或等价的真实 RAG 评测实现

LangGraph 用于 Agent 状态与控制流，而不是简单包装几个顺序函数。

## 3.3 前端

推荐：

- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- PDF.js 或成熟 PDF 阅读组件
- TanStack Query 或等价的数据请求管理方案

支持响应式布局和流式聊天。

## 3.4 模型支持

构建统一 Model Provider 抽象。

支持 OpenAI-compatible API，允许设置：

- Base URL
- API Key
- Chat Model
- Embedding Model
- Reranker
- Temperature
- Context Length
- Timeout
- Retry Policy

Embedding 和 Reranker 应支持 API 及本地模型实现。

不能把所有调用绑定到单一模型供应商。

所有密钥必须使用环境变量或服务端安全配置。

## 3.5 部署

- Docker
- Docker Compose
- PostgreSQL 持久化
- Qdrant 持久化
- Redis
- 独立 Background Worker
- Nginx / Caddy
- HTTPS 配置说明
- 健康检查
- 环境变量管理

本地开发和生产部署配置应分离。

---

# 4. 系统架构

系统设计为六层。

## Layer 1：Web Application

负责：

- 用户身份认证
- 知识库管理
- 论文上传
- AI Research Chat
- PDF 阅读
- 实验记录浏览
- 跨论文比较
- 研究报告
- 评测结果展示

## Layer 2：Application API

FastAPI 提供：

- 认证 API
- Paper API
- Library API
- Retrieval API
- Experiment API
- Research Agent API
- Evaluation API

## Layer 3：Research Agent

LangGraph 负责：

- Query Classification
- Query Planning
- Tool Selection
- Retrieval
- Evidence Aggregation
- Experiment Comparison
- Answer Generation
- Evidence Verification
- Retry / Fallback

## Layer 4：Retrieval & Analysis

包含：

- Dense Retriever
- BM25 Retriever
- Hybrid Fusion
- Reranker
- Structured Experiment Retriever
- Experiment Extractor
- Comparability Engine
- Claim–Evidence Validator

## Layer 5：Data Processing

包含：

- PDF Parser
- Layout Processor
- Table Extractor
- Section-Aware Chunker
- Metadata Extractor
- Background Ingestion Worker

## Layer 6：Storage & Observability

包含：

- PostgreSQL
- Qdrant
- 文件存储
- Redis
- Langfuse
- 结构化日志

禁止模块之间形成难以维护的循环依赖。

---

# 5. 核心模块 A：Experiment-Aware RAG

这是第一项重点研发功能。

## 5.1 PDF 解析

使用 Docling。

必须处理：

- 学术论文双栏排版
- 标题及章节
- 正文
- 表格
- 图表标题
- 公式文本或结构化表示
- 页码
- 阅读顺序
- 文档来源位置

优先采用 Docling 的结构化输出。

对于无法直接处理的公式和复杂图片，应保留引用位置，并标记解析能力限制。

不要假装能够完美理解所有图像。

PDF 解析必须作为后台任务执行。

## 5.2 Section-Aware Chunking

普通固定长度切分会破坏论文的逻辑结构。

实现章节感知分块：

- Abstract
- Introduction
- Related Work
- Method
- Experiments
- Results
- Ablation
- Conclusion
- Appendix

保留章节层次。

对于表格：

- 记录 Table ID
- Caption
- 页码
- 表头
- 行信息
- 列信息
- 单元格内容
- 单元格与行列标题的关联

长表格允许分块，但不得丢失原始行列关系。

## 5.3 多层级索引

构建三个互补索引。

### Paper Index

存储论文级语义与元数据。

用于确定哪些论文与问题相关。

### Chunk / Evidence Index

存储章节、段落、表格说明和其他证据单元。

用于寻找原始答案证据。

### Experiment Index

存储结构化实验记录及可供检索的规范化描述。

用于对模型、数据集、指标和实验条件进行精确过滤。

Experiment 数据的权威记录存储在 PostgreSQL。

Qdrant 只用于相关向量检索，不应成为业务实体和实验条件的唯一数据源。

## 5.4 混合检索

实现：

1. Dense Retrieval
2. BM25 Retrieval
3. Hybrid Search
4. RRF Fusion
5. Reranking
6. Metadata Filtering

BM25 必须使用真正的 BM25 算法或明确实现的 BM25 稀疏表示。

不得将简单字符串匹配冒充 BM25。

RRF 实现应可以独立测试。

## 5.5 Structured Retrieval

这是区别于普通 RAG 的核心。

例如查询：

“找出所有在 2.5-bit 下评测 PIQA 的 MoE 量化方法。”

系统应能够把自然语言条件解析为结构化过滤：

- Model Family / Architecture
- Dataset
- Metric
- Bit Precision
- Quantization Scope

先查询符合约束的实验记录，再读取关联证据。

对于模型没有提供的条件，不能自行创造。

允许结合结构化 SQL 查询与语义检索。

所有结构化查询必须参数化、经过字段白名单验证，并施加用户权限范围。

不要让 LLM 直接执行任意 SQL。

## 5.6 Query Router

识别不同问题：

- Basic QA
- Paper Lookup
- Section Retrieval
- Experiment Lookup
- Cross-Paper Comparison
- Literature Research

根据任务选择合适的检索路径。

简单问题不要无条件运行多步骤 Agent。

---

# 6. 核心模块 B：结构化实验数据抽取

这是项目最重要的业务能力之一。

## 6.1 Experiment Record Schema

使用 Pydantic 定义严格的结构化数据模型。

每条实验记录至少包含：

### Identity

- experiment_id
- paper_id
- method_name
- experiment_group
- source_type
- extraction_version

### Model

- model_name
- model_version
- model_size
- model_architecture
- model_checkpoint

### Dataset

- dataset_name
- dataset_version
- dataset_split
- evaluation_protocol

### Measurement

- metric_name
- metric_value
- metric_unit
- metric_direction
- metric_definition

### Quantization

- quantization_method
- precision_type
- bit_width
- average_bits
- quantized_components
- quantization_scheme
- calibration_method
- calibration_samples

### Experimental Setup

- seed_count
- reported_variance
- inference_settings
- hardware
- baseline_name
- additional_conditions

### Provenance

- paper_id
- page_number
- section_name
- table_id
- row_identifier
- column_identifier
- original_value
- original_text
- evidence_ids

### Quality Control

- extraction_status
- extraction_confidence
- verification_status
- review_status
- warnings

所有可能缺失的字段都需要显式支持 `null` 或相应的 Unknown 状态。

数值、单位、实验条件不能在没有证据时自动补全。

## 6.2 实验信息抽取流程

实现流水线：

PDF → Section Recognition → Experiment Section Detection → Table/Paragraph Parsing → LLM Structured Extraction → Schema Validation → Evidence Alignment → PostgreSQL。

要求：

- 使用 Structured Output
- 校验字段类型
- 规范化常见模型和数据集名称
- 规范化指标单位
- 保留原始字段
- 保留提取前后的映射
- 可批量处理
- 支持失败重试
- 支持人工修订

不能将 `0.79`、`79%`、`79.0` 混为相同量纲而不记录单位与语义。

应通过明确的数值规范化规则处理。

对于存在 ±、置信区间、标准差或多次实验的结果，保留对应统计信息。

## 6.3 表格理解

必须尽可能正确处理：

- 多级列标题
- 多级行标题
- 合并单元格
- 加粗最佳值
- 表格脚注
- 特殊符号
- 百分比
- Mean ± Std
- 不同精度或模型的分组

对于跨页表格或无法明确恢复结构的表格，应记录解析限制，进入人工审核或降级流程。

不允许在不确定时默默生成数值。

## 6.4 Evidence Mapping

每个提取字段需要保存原始证据来源。

例如：

`metric_value = 79.2`

需要能够关联：

- Paper ID
- Table 3
- 第 7 页
- PIQA 列
- Method A 行
- 原始数值单元格

如果无法定位到具体单元格，至少关联原始证据片段，并明确标注定位精度。

不允许伪造 PDF 页码或表格单元格坐标。

## 6.5 数据一致性与版本管理

实现：

- 论文级去重
- 实验记录去重
- 重复抽取的幂等处理
- 抽取模型版本记录
- Schema 版本记录
- 用户修订记录
- 重新索引
- 删除同步清理

用户能够查看 AI 原始提取结果与人工修订结果。

---

# 7. 核心模块 C：Experiment Comparability Engine

目标：判断跨论文结果是否具备公平比较条件。

采用：

**LLM 提取 + Schema 标准化 + Rule-Based Validation + LLM Explanation**

## 7.1 比较维度

至少支持：

1. Model Name
2. Model Checkpoint / Version
3. Dataset
4. Dataset Split
5. Evaluation Metric
6. Metric Definition
7. Quantization Precision
8. Quantization Scope
9. Calibration Configuration
10. Evaluation Protocol
11. Reported Statistical Setting

对于特定研究领域可以扩展比较规则。

不同领域可能存在不同的关键控制变量，不能将一套规则强行适用于所有科学领域。

## 7.2 比较结果

建议使用结构化内部状态：

- `COMPARABLE`
- `PARTIALLY_COMPARABLE`
- `NOT_COMPARABLE`
- `INSUFFICIENT_INFORMATION`

其中：

**COMPARABLE**

已核对所有预定义的关键条件，未发现破坏可比性的差异。

这并不意味着因果上完全公平，也不意味着足以判断统计显著性。

**PARTIALLY_COMPARABLE**

存在部分差异，但仍可以在明确限制的条件下进行描述性比较。

**NOT_COMPARABLE**

存在明确的不兼容条件，使直接数值排名缺乏意义。

**INSUFFICIENT_INFORMATION**

缺少足够的实验条件，无法作出可靠判断。

不要把 Unknown 自动归类为 Comparable。

## 7.3 Rule Engine

实现可配置规则系统。

规则应区分：

- Required Fields
- Hard Constraints
- Soft Constraints
- Missing Information
- Domain-Specific Constraints

例如：

同一任务但评价指标不一致，通常不能直接比较原始数值。

相同模型但平均 Bit 不一致，不能宣称是等预算比较。

量化范围不同，例如仅专家权重量化和全模型量化，必须单独说明。

不同校准集、校准样本数或后处理设置会影响严格实验控制，但不应在所有场景下一律判定完全不可比较。

不同研究领域的规则必须能够配置和扩展。

## 7.4 比较输出

返回：

- Comparison Status
- Matched Conditions
- Mismatched Conditions
- Missing Conditions
- Relevant Evidence
- Warnings
- Human-Readable Explanation

前端展示每个字段的比较结果。

允许用户点击字段查看原始论文中的对应证据。

## 7.5 比较示例

假设：

论文 A：

- Model：Qwen3-30B-A3B
- Dataset：PIQA
- Average Bits：2.50
- Metric：Accuracy
- Calibration Samples：512
- Result：78.2%

论文 B：

- Model：Qwen3-30B-A3B
- Dataset：PIQA
- Average Bits：2.50
- Metric：Accuracy
- Calibration Samples：128
- Result：79.1%

这些数值仅为测试用虚构样例。

系统应该指出：

论文 B 报告的准确率数值较高，但校准样本数不同，因此不能将其视为严格受控条件下的性能优势证明。

必须通过自动化测试验证这个行为。

---

# 8. 核心模块 D：Claim–Evidence Verification

建立可审计的科研回答生成流程。

## 8.1 Claim Extraction

将最终回答拆解为可验证的原子声明。

例如：

“论文 A 使用 2.5-bit 量化，并在 PIQA 上获得 79.2% Accuracy。”

可以拆成：

- 论文 A 使用 2.5-bit。
- 论文 A 在 PIQA 上进行了评测。
- 对应 Accuracy 为 79.2%。

## 8.2 Evidence Retrieval

为每个 Claim 收集证据。

证据可能来自：

- 正文段落
- 实验表格
- 图表标题
- 方法章节
- 附录

## 8.3 Deterministic Verification

对可以形式化的内容进行规则验证。

包括：

- 数值精确匹配
- 单位转换
- 数据集名称匹配
- 模型名称匹配
- 指标名称匹配
- Precision 匹配
- Evidence ID 有效性
- 用户是否有权访问证据

不应依赖 LLM 主观评分完成所有校验。

## 8.4 Semantic Verification

对于无法使用简单规则判断的复杂语义声明，允许调用独立 LLM Judge 或 NLI 模型。

输出：

- Supported
- Contradicted
- Insufficient Evidence

必须保留评判依据和不确定性。

不能把 LLM Judge 判断当作绝对事实。

## 8.5 Citation Grounding

回答中的每个关键声明都应关联具体证据 ID。

Citation ID 必须由服务端生成和验证。

不能接受模型随意编造的引用编号。

用户点击引用时：

- 打开正确论文
- 定位到正确页码
- 展示证据片段
- 对支持的文件类型尽可能高亮证据位置

如果无法可靠定位精确区域，可以跳转到页码并展示证据文本，但不能显示虚假的高亮区域。

## 8.6 校验失败处理

若发现明显不被证据支持的数值声明：

1. 尝试有限次数的修正。
2. 重新读取相关证据。
3. 重新生成对应部分。
4. 仍无法确认时删除该声明或明确说明证据不足。

设置有限的验证次数，避免无限循环。

---

# 9. LangGraph Research Agent

系统必须实现真正的 Agentic RAG。

不过，不应为了使用多 Agent 而引入不必要的复杂度。

优先实现可观测、可测试、具有条件路由的单 Agent 状态图。

## 9.1 State

定义包含以下信息的 Agent State：

- User Query
- User ID
- Library Scope
- Conversation ID
- Task Type
- Search Plan
- Search Queries
- Retrieved Papers
- Retrieved Evidence
- Experiment Records
- Comparison Result
- Claims
- Verification Result
- Tool Call Count
- Retry Count
- Budget
- Final Answer
- Citations
- Errors

需要明确持久化字段与临时字段的区别。

## 9.2 节点设计

实现：

**Intent Classifier**

判断问题类型。

**Query Planner**

对复杂研究任务进行拆解。

**Paper Retriever**

检索相关论文。

**Evidence Retriever**

检索原始证据。

**Experiment Retriever**

查询结构化实验记录。

**Comparability Tool**

执行实验条件校验。

**Evidence Evaluator**

检查检索证据是否充足。

**Answer Generator**

生成带引用的回答。

**Claim Verifier**

核验关键事实和数值。

**Retry / Fallback Controller**

管理重试、退出和失败回退。

## 9.3 Agent Tools

实现清晰的工具接口：

- `search_papers`
- `retrieve_evidence`
- `get_paper_metadata`
- `get_paper_sections`
- `query_experiments`
- `compare_experiments`
- `verify_claims`
- `search_public_papers`

所有工具使用 Pydantic Schema。

每个工具必须定义：

- 输入参数
- 输出结构
- 错误类型
- 超时
- 权限验证
- 日志追踪

## 9.4 动态流程

对于简单问答：

Query → Retriever → Answer。

对于实验查询：

Query → Experiment Retriever → Evidence → Answer。

对于跨论文比较：

Query → Planner → Experiment Retrieval → Comparability Engine → Evidence Verification → Answer。

对于复杂研究报告：

Query → Planner → Multiple Retrieval Tasks → Evidence Aggregation → Structured Analysis → Claim Verification → Report。

所有循环必须具有：

- 最大次数
- Token 预算
- 超时
- 失败出口

不能让 Agent 无限调用工具。

## 9.5 流式输出

使用 SSE。

前端可以看到：

- 当前任务状态
- 检索阶段
- 分析阶段
- 回答 Token
- 最终引用

不得将内部敏感状态或完整系统提示词通过 SSE 返回给用户。

---

# 10. 在线学术检索

接入：

- OpenAlex API
- 可选 Semantic Scholar API

支持：

- 关键词查询
- 论文标题查询
- 作者查询
- 年份范围
- DOI
- arXiv ID
- 元数据导入

处理：

- Rate Limit
- 429
- 超时
- 分页
- 去重
- 缺失字段
- 失败重试

严格区分：

- 只有论文元数据
- 只有摘要
- 有权访问完整 PDF
- 已经完整解析并索引

不能把搜索结果的摘要当成完整论文实验数据。

下载全文时必须尊重许可与访问限制。

该功能属于第二阶段增强功能，不应阻碍核心本地 RAG 系统交付。

---

# 11. 数据库设计

使用 PostgreSQL。

核心表建议包括：

- users
- libraries
- library_memberships
- papers
- paper_files
- paper_sections
- paper_chunks
- paper_tables
- paper_table_cells
- experiments
- experiment_conditions
- evidence
- extraction_jobs
- extraction_revisions
- comparisons
- comparison_conditions
- conversations
- messages
- message_citations
- evaluation_datasets
- evaluation_runs

根据实际关系适当调整。

要求：

1. 正确设计主键、外键和索引。
2. 使用 Alembic Migration。
3. 重要业务实体有稳定 ID。
4. 删除论文同步清理相关索引。
5. 处理文件上传和索引任务的局部失败。
6. 支持幂等重新解析。
7. 保留必要的数据提取版本信息。
8. 支持不同用户的知识库权限隔离。

Qdrant 中保存：

- Chunk ID
- Paper ID
- Library ID
- 权限过滤所需的可靠元数据
- Vector
- Index Version

向量检索不能绕过用户权限。

---

# 12. 前端设计

这是一个完整产品，不是 Gradio 或 Streamlit 的临时演示页。

使用 Next.js + TypeScript。

界面风格：

- 现代化
- 简洁
- 专业
- 类似科研 AI 工作台
- 响应式布局
- 清晰的信息层级

避免无意义的炫酷动画。

## 12.1 Dashboard

展示：

- 论文总数
- 知识库数量
- 已提取实验记录数
- 最近论文
- 最近研究任务
- 处理状态

## 12.2 Paper Library

支持：

- 创建知识库
- 上传 PDF
- 删除论文
- 查看解析状态
- 查看论文元数据
- 搜索论文
- 打开 PDF 阅读器

## 12.3 AI Research Chat

提供：

- 流式回答
- Markdown
- 多轮对话
- 引用点击
- 论文筛选
- 检索模式切换
- 对话历史
- 当前研究步骤

## 12.4 Experiment Explorer

这是最重要的差异化页面。

展示所有结构化实验记录。

支持根据以下字段筛选：

- Paper
- Method
- Model
- Dataset
- Metric
- Bit Width
- Average Precision

用户点击某条实验记录，可以看到：

- 结构化数据
- 来源论文
- 来源页码
- 来源表格
- 原始证据
- 抽取置信度与审核状态

支持用户修订自动提取结果。

## 12.5 Experiment Comparison

选择两组或多组实验。

系统显示：

- 结果对照
- 逐字段匹配情况
- 不一致条件
- 缺失条件
- 可比性结论
- 对应证据
- AI 解释

比较状态必须反映真实后端校验结果，而不是前端硬编码。

## 12.6 Research Reports

支持生成研究报告。

输出：

- 研究问题
- 搜索范围
- 相关论文
- 方法分类
- 实验对比
- 结论
- 证据和局限性

支持 Markdown 导出。

PDF 导出可以作为后续增强。

## 12.7 Settings

提供：

- 个人资料
- 模型配置状态
- 检索参数
- 用户知识库
- 系统使用统计

API Key 不应直接暴露在前端。

---

# 13. 核心评测体系

项目必须具有可复现实验，不得只通过 Demo 演示证明质量。

## 13.1 Benchmark

构建：

**ML Experiment QA Benchmark**

第一版建议目标：

- 至少 30 篇真实机器学习论文
- 至少 150 条人工核验实验记录
- 至少 100 道真实问答和比较题

这是目标规模，不代表可以虚构数据。

先提供小型可运行评测集，再逐步扩展。

人工标注应至少经过人工核查，并记录标注方式和质量限制。

## 13.2 问题类型

涵盖：

- Fact Extraction
- Numerical QA
- Table QA
- Experiment Configuration QA
- Cross-Paper Comparison
- Multi-Hop Evidence Retrieval
- Unanswerable Questions
- Citation Verification

## 13.3 检索评测

实现：

- Recall@5
- Recall@10
- MRR
- nDCG@10

区分 Paper-level、Chunk-level 和 Experiment-level 的检索质量。

## 13.4 结构化提取评测

实现：

- Field-Level Precision
- Field-Level Recall
- Field-Level F1
- Experiment Record Exact Match
- Numeric Exact Match
- Unit Normalization Accuracy
- Evidence Alignment Accuracy

需要明确定义匹配规则。

对于名称别名、单位转换和数值精度，使用透明、可复现的规范化逻辑。

## 13.5 Comparability 评测

实现：

- Classification Accuracy
- Macro F1
- Per-Class Precision / Recall
- Unknown Detection Accuracy
- Explanation Evidence Accuracy

需要专门设计包含条件差异和缺失信息的测试集。

## 13.6 Claim Verification 评测

实现：

- Citation Validity
- Evidence Support Precision
- Numerical Claim Accuracy
- Unsupported Claim Rate

对于部分自动评测使用 LLM Judge 的场景，必须明确模型评估存在误差。

至少抽取部分结果进行人工检查。

## 13.7 端到端评测

对比以下方案：

**Baseline A：Dense RAG**

只使用普通向量检索。

**Baseline B：Hybrid RAG**

Dense + BM25 + RRF。

**Baseline C：Hybrid RAG + Reranker**

标准检索增强方案。

**Baseline D：Standard Agentic RAG**

加入查询规划和迭代检索，但不使用结构化实验检索。

**PaperMind A：Experiment-Aware RAG**

增加结构化实验数据查询。

**PaperMind B：Experiment-Aware RAG + Comparability Engine**

增加实验条件校验。

**PaperMind Full：全部模块**

增加 Claim–Evidence Verification。

每个版本尽量采用：

- 相同论文库
- 相同问题
- 相同 Embedding
- 相同生成模型
- 相同模型配置
- 记录所有额外工具调用

比较 Accuracy、Latency、Token 和 Cost。

不能只报告准确率而忽视工程成本。

实验应明确区分：

1. 额外结构化索引带来的离线处理成本。
2. 在线查询耗时。
3. 生成模型成本。
4. 额外验证模型调用成本。

## 13.8 实验结果

必须生成：

- `evaluation/results/*.json`
- `evaluation/results/*.csv`
- `docs/evaluation-report.md`

绘制真实实验图表。

图表至少包含：

- 检索模式效果比较
- 不同模块消融结果
- 延迟比较
- 成本比较

不得编造任何实验结果。

---

# 14. 可观测性

使用 Langfuse 或兼容的 OpenTelemetry 方案。

记录：

- Request ID
- Trace ID
- Agent Node
- Tool Calls
- Retrieval Latency
- Reranking Latency
- LLM Latency
- Input Tokens
- Output Tokens
- Cost
- Retry Count
- Error Type
- End-to-End Latency

支持查看 Agent 各节点执行轨迹。

日志中不得默认记录秘密、私人完整论文、凭据或其他敏感内容。

将模型调用日志与普通业务日志区分。

---

# 15. API 设计

统一前缀：

`/api/v1`

至少实现：

## Authentication

- POST `/auth/register`
- POST `/auth/login`
- GET `/auth/me`

## Libraries

- GET `/libraries`
- POST `/libraries`
- GET `/libraries/{id}`
- PATCH `/libraries/{id}`
- DELETE `/libraries/{id}`

## Papers

- POST `/papers/upload`
- GET `/papers`
- GET `/papers/{id}`
- GET `/papers/{id}/status`
- GET `/papers/{id}/file`
- DELETE `/papers/{id}`

## Retrieval

- POST `/search`
- POST `/search/experiments`

## Experiments

- GET `/experiments`
- GET `/experiments/{id}`
- PATCH `/experiments/{id}`
- POST `/experiments/compare`

## Research

- POST `/research/chat`
- POST `/research/chat/stream`
- POST `/research/report`
- GET `/research/conversations`

## Evaluation

- POST `/evaluation/run`
- GET `/evaluation/runs`
- GET `/evaluation/runs/{id}`

允许根据实际 REST 设计做合理调整。

所有接口必须：

- 使用 Pydantic
- 具有明确 Schema
- 使用统一错误结构
- 具有权限验证
- 具有必要的分页
- 支持 OpenAPI 文档

---

# 16. 安全与可靠性

这是可公开部署的服务。

至少实现：

- 安全认证
- 密码哈希
- 资源级授权
- 用户知识库隔离
- 文件类型验证
- 文件大小限制
- 路径安全
- 速率限制
- CORS 白名单
- SQL 参数化
- 向量检索权限过滤
- 敏感配置隔离
- API 调用超时
- 成本预算
- 后台任务幂等性
- 删除和失败恢复

特别注意：

论文 PDF、论文摘要、在线网页和检索结果都是不可信数据。

必须防止 Prompt Injection 通过这些内容影响系统级行为。

不能让论文内容触发未经授权的工具调用、跨用户数据访问或系统命令执行。

外部 URL 下载必须防护 SSRF。

不要让用户输入的路径或 URL 被直接传递给不受限的文件系统及网络操作。

---

# 17. 项目文件结构

采用 Monorepo。

建议：

`papermind/`

- `backend/`
  - `app/`
    - `api/`
    - `core/`
    - `models/`
    - `schemas/`
    - `repositories/`
    - `services/`
    - `ingestion/`
    - `retrieval/`
    - `experiments/`
      - `schemas/`
      - `extraction/`
      - `normalization/`
      - `comparability/`
      - `verification/`
    - `agents/`
      - `state.py`
      - `nodes/`
      - `tools/`
      - `graphs/`
    - `evaluation/`
    - `tasks/`
    - `main.py`
  - `alembic/`
  - `tests/`
  - `pyproject.toml`
  - `Dockerfile`
- `frontend/`
  - `app/`
  - `components/`
  - `features/`
  - `lib/`
  - `types/`
  - `Dockerfile`
- `evaluation/`
  - `datasets/`
  - `baselines/`
  - `scripts/`
  - `results/`
- `docs/`
  - `architecture.md`
  - `api.md`
  - `data-model.md`
  - `evaluation-report.md`
  - `deployment.md`
  - `decisions/`
  - `portfolio/`
- `scripts/`
- `docker-compose.yml`
- `.env.example`
- `.gitignore`
- `README.md`
- `PROGRESS.md`

可以根据实际架构调整，但必须保持清晰职责。

---

# 18. 开发阶段

这是必须遵循的执行计划。

## Phase 0：项目初始化

任务：

1. 检查当前工作目录。
2. 检查是否存在已有项目文件。
3. 检查 Python、Node.js、Docker 和 Git。
4. 核实核心库当前稳定版本及官方 API。
5. 设计系统架构。
6. 设计数据库。
7. 创建项目目录。
8. 创建 `.env.example`。
9. 创建 `PROGRESS.md`。
10. 编写初始 README。

验收：

- 项目结构合理
- 基础开发环境能够启动
- 架构和数据模型有明确文档

不要在完成方案后停止，继续下一阶段。

## Phase 1：基础论文 RAG

实现：

- FastAPI
- PostgreSQL
- Qdrant
- 用户认证
- 论文库管理
- PDF 上传
- Docling 解析
- Chunking
- Dense Retrieval
- 引用问答
- 基础 Web UI
- Docker 基础部署

验收：

用户可以通过浏览器上传真实 PDF，并对论文提问，获得真实证据支持的回答。

## Phase 2：高级检索

实现：

- BM25
- Hybrid Retrieval
- RRF
- Reranker
- Query Rewrite
- Retrieval Benchmark

验收：

不同检索模式均可以正常运行，并执行可复现的对比实验。

## Phase 3：实验结构化提取

实现：

- 实验章节识别
- 表格解析
- 实验记录提取
- Pydantic Schema
- 数据规范化
- Evidence Mapping
- Experiment Database
- Experiment Explorer UI

验收：

上传包含实验表格的真实机器学习论文后，可以查询结构化实验数据，并定位其原始证据。

## Phase 4：Comparability Engine

实现：

- 条件规范化
- 规则配置
- 硬约束与软约束
- 缺失字段识别
- 比较结果生成
- 解释报告
- 比较界面
- 自动化测试

验收：

系统能够正确识别相同条件、条件差异和信息缺失的案例。

不能将不同 Average Bits 的量化结果自动视为严格等预算比较。

## Phase 5：Claim–Evidence Verification

实现：

- Claim Extraction
- 数值校验
- 证据 ID 校验
- 语义校验接口
- 引用追溯
- 验证失败处理
- Citation Viewer

验收：

系统能够检测至少以下错误：

- 引用不存在
- 指标名称不一致
- 实验数值不匹配
- 数据集不匹配
- 模型不匹配
- 无证据支持的结论

## Phase 6：Research Agent

实现：

- LangGraph State
- Query Classification
- Planning
- Retrieval Tools
- Experiment Query Tools
- Comparison Tools
- Evidence Verification Tools
- Conditional Routing
- Retry / Fallback
- Streaming
- Persistence
- Langfuse Tracing

验收：

复杂跨论文问题可以经过多步检索与结构化分析生成回答。

执行轨迹能够被查看。

Agent 不发生无限循环。

## Phase 7：完整 Web 产品

完善：

- Dashboard
- Paper Library
- Research Chat
- Experiment Explorer
- Experiment Comparison
- Research Reports
- Settings
- 用户体验
- 加载状态
- 错误提示
- PDF 阅读器
- 引用定位

验收：

全部核心页面可以真实调用后端 API，不存在只有外观没有功能的按钮。

## Phase 8：Benchmark 与性能优化

实现：

- 真实评测数据集
- 检索指标
- 实验提取指标
- 比较分类指标
- Claim Verification 指标
- 消融实验
- 成本统计
- 延迟评测
- 实验报告

验收：

能够使用脚本复现实验，并输出实际指标。

如完整目标规模需要人工标注，应报告已完成样本数量和剩余部分，不能虚构人工标注。

## Phase 9：完整部署

完成：

- Docker Compose
- 数据库迁移
- 环境变量
- 持久化
- 健康检查
- 日志
- HTTPS 部署说明
- 生产配置
- 安全检查
- 端到端测试

验收：

具备从空环境部署的完整步骤。

有可用 Docker 环境时，应实际验证容器启动与主要业务流程。

实际公网部署依赖用户提供服务器、域名及必要凭据，不能虚构线上运行成功。

## Phase 10：简历交付材料

在 `docs/portfolio/` 下生成：

- 项目架构说明
- 核心技术亮点
- RAG 技术实现细节
- LangGraph Agent 说明
- 实验感知 RAG 设计
- Comparability Engine 设计
- Claim Verification 设计
- 性能对比结果
- 部署说明
- 演示脚本
- 面试问题与答案
- 中英文简历描述

所有简历数字必须来自真实实验结果。

---

# 19. 自动化测试

必须建立真实的自动化测试体系。

## 19.1 后端测试

使用 pytest。

覆盖：

- 用户认证
- 权限隔离
- 知识库 CRUD
- PDF 上传验证
- PDF 解析
- Chunking
- Embedding
- Qdrant 检索
- BM25
- RRF
- Reranker
- Experiment Extraction
- Schema Validation
- Numeric Normalization
- Experiment Comparison
- Missing Field Handling
- Claim Verification
- Citation Validation
- LangGraph Routing
- Retry Limit
- Tool Failure
- Conversation Persistence
- 数据删除与索引清理

## 19.2 核心业务测试

需要建立真实或明确标记为合成测试数据的固定 Fixture。

测试案例包括：

**Test 1：完全一致的实验条件**

应能输出 COMPARABLE，并列出匹配依据。

**Test 2：Average Bits 不同**

不得输出严格等预算比较结论。

**Test 3：Metric 不同**

不得直接比较原始数值。

**Test 4：Calibration Samples 不同**

应在适当场景标记限制条件。

**Test 5：模型版本未知**

不得假设版本一致。

**Test 6：论文表格数值抽取错误**

校验模块应检测错误或标记需要审核。

**Test 7：不存在的 Citation**

必须拒绝无效引用。

**Test 8：跨用户访问**

用户 B 无法读取用户 A 的私人论文及实验记录。

**Test 9：Agent 无限循环防护**

达到预算后必须退出。

**Test 10：结构化索引重复构建**

不会无控制地产生重复实验记录。

## 19.3 端到端测试

至少实现：

注册 → 创建知识库 → 上传论文 → 解析 → 检索 → 提取实验记录 → 比较实验 → 获取引用 → 查看原文。

测试过程中允许使用测试模型或 Fixture，但必须明确标注，并额外验证至少一个真实模型调用流程。

---

# 20. 工程质量要求

后端：

- 类型标注
- Pydantic 校验
- 合理分层
- 异步 I/O
- 结构化异常
- 数据库迁移
- 依赖版本锁定
- 安全配置

前端：

- TypeScript
- 明确组件边界
- 无无效交互
- 加载与错误状态
- API 类型定义
- 响应式布局

运行质量：

- 不存在明显的死循环
- 不存在没有边界的模型重试
- 不存在跨用户数据泄漏
- 不存在直接暴露密钥
- 不存在假引用
- 不存在伪造的性能指标
- 不存在阻止核心流程运行的未处理异常

优先完善核心流程，而不是盲目增加功能。

---

# 21. 最终交付标准

最终必须提供：

1. 完整项目源码
2. 前端 Web 应用
3. FastAPI 后端
4. PostgreSQL 数据库及迁移
5. Qdrant 向量数据库集成
6. 论文上传和 Docling 解析
7. Dense + BM25 + RRF + Reranker
8. 结构化实验数据提取
9. Experiment Comparability Engine
10. Claim–Evidence Verification
11. LangGraph Research Agent
12. 用户与知识库权限管理
13. 基础在线论文搜索
14. RAG 自动评测
15. 端到端测试
16. Docker 部署文件
17. 完整 README
18. API 文档
19. 系统架构说明
20. 简历项目材料

对每一项标记：

- PASS：实际测试通过
- PARTIAL：部分完成
- FAIL：未通过
- BLOCKED：受外部环境约束

必须提供证据，例如测试输出、代码路径、运行命令或真实实验文件。

不要仅根据代码存在就宣称功能已经验证成功。

---

# 22. 开源与独立性要求

本项目参考 PaperQA2、ScholarQA、LangGraph、Docling、Qdrant 等开源项目。

但是：

- 不要整体复制某个开源应用并仅修改界面。
- 必须遵守第三方许可证。
- 必须在 README 中明确依赖和参考来源。
- 必须自主实现实验记录抽取流程的业务编排。
- 必须自主实现实验条件比较规则。
- 必须实现自己的证据关联和校验模块。
- 必须拥有可复现的评测框架。
- 不得声称行业首创，除非有充分证据。

项目差异化来自经过验证的功能设计与工程实现，不依赖营销式命名。

---

# 23. 优先级与资源约束

假设项目初期部署在普通云服务器，模型通过外部 API 调用。

不要默认服务器拥有高性能 GPU。

必须提供轻量运行方案。

## P0 — 绝对优先

- 用户与论文库
- PDF 解析
- Hybrid RAG
- 引用溯源
- Experiment Extraction
- Experiment Explorer
- Comparability Engine
- 基础 Claim Verification
- LangGraph Agent
- 基础 Web UI
- Docker
- 自动化测试

## P1 — 高优先级

- 在线论文搜索
- 高级表格理解
- 文献综述
- 完整 Benchmark
- Langfuse
- 多轮对话
- 性能优化

## P2 — 可延后

- 复杂知识图谱
- 多 Agent 协作
- 图表数值自动读取
- 高级 PDF 可视化标注
- 高级报告导出
- 分布式部署
- 大规模高并发优化

**不能为了实现 P2 而影响 P0 的可靠性。**

---

# 24. Coding Agent 持续开发机制

你可能无法在单个上下文窗口中完成整个项目。

因此必须使用持久化开发记录。

`PROGRESS.md` 至少包括：

- 当前 Phase
- 已完成任务
- 未完成任务
- 关键架构决策
- 修改过的核心文件
- 当前可以运行的命令
- 最近测试结果
- 已知问题
- 下一步任务
- 外部依赖阻塞

每次启动新的开发会话时，优先：

1. 读取 `PROGRESS.md`。
2. 查看当前 Git 状态。
3. 查看最近修改。
4. 检查项目测试。
5. 确定下一项未完成任务。
6. 继续编码。

不要重新生成已经稳定工作的模块。

不要在每个阶段之后停下并等待用户选择下一步，除非确实需要用户提供外部凭据、授权或关键产品决策。

在工具允许的范围内，尽可能完成当前环境可以验证的工作。

---

# 25. 最终面试价值要求

最终项目需要支持以下面试问题的深入讨论：

1. 为什么选择 Agentic RAG？
2. 普通 RAG 为什么不适合复杂实验数据查询？
3. Dense Retrieval 和 BM25 有什么区别？
4. RRF 如何融合多个检索器？
5. Reranker 的作用和成本是什么？
6. 为什么需要结构化实验索引？
7. 为什么不能仅依赖 LLM 做实验公平比较？
8. 如何设计 Comparability Engine？
9. 如何解决实验字段缺失问题？
10. 如何保证数值不被 LLM 编造？
11. 如何将引用定位到原始 PDF？
12. 如何处理复杂双栏论文和实验表格？
13. LangGraph State 如何设计？
14. Agent 如何决定下一步操作？
15. Agent 如何避免无限 Tool Calling？
16. 如何实现跨用户向量检索隔离？
17. 如何实现 PDF 异步解析？
18. 如何进行 RAG 系统的消融实验？
19. 为什么 Agentic RAG 不一定比普通 RAG 好？
20. 如何控制模型调用成本与系统延迟？
21. 如何设计完整的线上部署方案？
22. 与 PaperQA2、ScholarQA 等项目相比，PaperMind 的实际工程差异在哪里？
23. 哪些模块由自己实现，哪些复用了开源组件？
24. 实验中哪一项改进带来的收益最大？
25. 当前系统有哪些不足，下一步如何改进？

必须让这些问题的答案能够回溯到真实代码和评测结果。

---

# 26. 现在立即开始

你现在拥有完整的项目要求。

**不要再次输出长篇项目规划代替实际开发。**

立即执行以下操作：

1. 检查当前工作目录和开发环境。
2. 检查已有文件，避免覆盖用户工作。
3. 核实必要依赖的官方文档与兼容性。
4. 创建项目结构。
5. 建立 PostgreSQL、FastAPI、Qdrant 的基础架构。
6. 实现真实 PDF 上传与解析。
7. 实现第一个可以端到端测试的论文 RAG 问答流程。
8. 运行测试并修复错误。
9. 更新 `PROGRESS.md`。
10. 按开发阶段继续实现 Experiment-Aware RAG、Comparability Engine、Claim Verification 和 LangGraph Agent。
11. 完成前端、评测、Docker 和项目文档。
12. 最后执行完整验收并如实报告结果。

核心任务始终是：

**把 PaperMind 开发成一个能够理解机器学习论文实验、验证跨论文比较条件、提供可信证据链的真实科研分析平台。**

不是只生成漂亮的 UI。

不是只调用一个向量数据库。

不是只写几个 LangChain 示例。

不是只输出计划。

**现在开始实际编码。**