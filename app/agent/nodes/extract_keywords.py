"""
关键词抽取节点

负责从用户自然语言问题中识别检索线索
后续字段召回 字段取值召回和指标召回都会基于这些关键词展开
"""

import sys
from pathlib import Path

# 支持直接作为脚本运行 (python app/agent/nodes/extract_keywords.py)
project_root = Path(__file__).resolve().parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import jieba.analyse
from langgraph.runtime import Runtime

from app.agent.context import DataAgentContext
from app.agent.state import DataAgentState
from app.core.log import logger


async def extract_keywords(state: DataAgentState, runtime: Runtime[DataAgentContext]):
    """抽取用户问题中的关键词，并通过流式输出反馈当前进度"""

    step = "抽取关键词"
    writer = runtime.stream_writer
    writer({"type": "progress", "step": step, "status": "running"})

    try:
        query = state["query"]

        # 只保留更可能承载业务含义的 12 类词性，过滤掉“的、帮我、一下”等无检索价值的噪声词
        allow_pos = (
            "n",    # 普通名词: 商品、订单、销售额
            "nr",   # 人名: 张三、李四
            "ns",   # 地名: 华北、北京、上海
            "nt",   # 机构团体名: 门店、品牌、渠道
            "nz",   # 其他专有名词: SKU、会员
            "v",    # 动词: 统计、对比、查询
            "vn",   # 名动词: 销售、成交、退款
            "a",    # 形容词: 新增、有效、活跃
            "an",   # 名形词: 可用、有效、异常
            "eng",  # 英文单词/缩写: GMV、SKU、ROI、AOV
            "i",    # 成语或习用语，避免遗漏整体表达
            "l",    # 常用固定短语，例如“销售总额”
        )

        # 1. 基于 TF-IDF 抽取关键词，并按 allowPOS 词性白名单过滤
        keywords = jieba.analyse.extract_tags(query, allowPOS=allow_pos)

        # 2. 【核心兜底策略】保留原始问题 query 作为保底检索入口，并用 set 去重！
        # 防止分词器切分不准时丢掉完整句子的上下文语义
        keywords = list(set(keywords + [query]))

        writer({"type": "progress", "step": step, "status": "success"})
        logger.info(f"抽取关键词成功: {keywords}")
        return {"keywords": keywords}
    except Exception as e:
        logger.error(f"抽取关键词失败: {e}")
        writer({"type": "progress", "step": step, "status": "error"})
        raise


if __name__ == "__main__":
    import asyncio
    from pprint import pprint

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    async def main():
        # 1. 模拟输入 state
        input_state: DataAgentState = {
            "query": "帮我统计一下华北地区的销售总额",
            "keywords": [],
            "retrieved_column_infos": [],
            "retrieved_metric_infos": [],
            "retrieved_value_infos": [],
            "error": None,
        }
        print("=== 1. 输入 State ===")
        pprint(input_state)

        # 2. 模拟 runtime (仅传入 stream_writer 接收流式进度)
        runtime = Runtime[DataAgentContext](stream_writer=lambda msg: print(f"[stream] {msg}"))

        # 3. 直接调用 extract_keywords 函数
        print("\n=== 2. 执行 extract_keywords 节点 ===")
        node_result = await extract_keywords(input_state, runtime)
        print("\n节点返回值 (更新增量):", node_result)

        # 4. 查看更新后的输出 state 结构
        output_state = {**input_state, **node_result}
        print("\n=== 3. 输出 State (更新后) ===")
        pprint(output_state)

    asyncio.run(main())


