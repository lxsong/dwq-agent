"""
电商问数 Agent 使用的大模型实例

集中初始化一个 OpenAI 兼容的 Chat Model，供节点或本地测试直接复用
"""

from langchain.chat_models import init_chat_model

from app.conf.app_config import app_config

# 统一从 app_config.llm 读取模型三件套 (model_name, base_url, api_key)
# 所有 Agent 节点直接 import 复用此 llm 实例，避免重复初始化
llm = init_chat_model(
    model=app_config.llm.model_name,
    # 硅基流动、DeepSeek、通义千问等主流平台均兼容 OpenAI 接口协议，故统一使用 openai provider
    model_provider="openai",
    base_url=app_config.llm.base_url,
    api_key=app_config.llm.api_key,
    # 【关键参数】将采样温度设为 0，关闭随机发散，确保 JSON 格式输出与 SQL 生成高度稳定可复现
    temperature=0,
)

if __name__ == "__main__":
    # 本地快速验证：测试 .env 中的 LLM_API_KEY 与 app_config.yaml 中的模型配置是否调通
    print(llm.invoke("你好").content)