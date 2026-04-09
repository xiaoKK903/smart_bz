# CHANGELOG

## 2026-04-09 — 核心链路串通重构

### 新增文件
- `core/intent.py` — 混合意图识别引擎（规则优先 + 启发式兜底），支持八字域8个意图 + 电商域7个意图
- `core/slot.py` — 通用槽位管理器，迁移旧项目完整的中文日期/时辰/性别解析，新增订单号/手机号提取
- `core/state.py` — 会话状态机（INIT→INTENT→SLOT_FILLING→PROCESSING→RESPONDING→COMPLETED/HANDOFF）
- `core/router.py` — 领域路由器，按意图分发到对应插件，启动时自动注册所有插件
- `domains/bazi/engine.py` — 真实排盘引擎（年月日时柱计算、五行统计、身旺身弱、用神忌神、格局分析、大运）
- `llm/prompt_builder.py` — 统一 Prompt 组装器
- `llm/token_counter.py` — Token 估算与截断
- `llm/fallback.py` — LLM 降级策略

### 重写文件
- `core/conversation.py` — **核心重写**，完整串通：输入过滤→意图识别→领域路由→槽位填充→上下文构建(插件+记忆+RAG)→Prompt组装→LLM调用→输出验证→插件后处理→记忆存储
- `domains/bazi/plugin.py` — 修复构造函数匹配基类、接口签名对齐、对接真实排盘引擎
- `domains/ecommerce/plugin.py` — 修复 import 路径、构造函数、添加 Mock 订单/物流数据

### 未修改（保持原样）
- `memory/` — 记忆系统（已完整）
- `guardrails/` — 安全护栏（已完整）
- `rag/` — RAG 检索（已有基础版）
- `config.py` / `main.py` — 配置和入口
- `llm/router.py` — LLM 路由（已可用）
