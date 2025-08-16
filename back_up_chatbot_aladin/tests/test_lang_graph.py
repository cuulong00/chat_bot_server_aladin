from langgraph.prebuilt import create_react_agent
from langchain.chat_models import init_chat_model
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AnyMessage
from langgraph.prebuilt.chat_agent_executor import AgentState
from langchain_core.runnables import RunnableConfig
from pprint import pprint
from pydantic import BaseModel
from typing import Annotated
import json

#gemma-3n-e4b-it

class ResponseAnswer(BaseModel):
    final_answer: str


class WeatherInput(BaseModel):
    city: str


def get_weather(input: WeatherInput) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {input.city}!"


# deepseek-r1-distill-llama-70b
model_deep_seek = ChatGroq(model="deepseek-r1-distill-llama-70b", temperature=0.5)
qwen = ChatGroq(model="qwen-qwq-32b", temperature=0.5)

model_gpt = init_chat_model(model="gpt-4o-mini")


def prompt(state: AgentState, config: RunnableConfig) -> list[AnyMessage]:
    user_name = config["configurable"].get("user_name")
    system_message = f"Bạn là trợ lý hữu ích. Hãy gọi người dùng là {user_name}.\
        Bạn sử dụng công cụ được cung cấp để trả lời câu hỏi của người dùng. \
        Lưu ý cực kỳ quan trọng là bạn chỉ chạy công cụ này một lần duy nhất. \
        Khi có kết quả, hãy trả về cho người dùng dưới dạng JSON với trường final_answer, ví dụ: {{'final_answer': 'Hà Nội đang mưa'}}."
    final_prompt = [{"role": "system", "content": system_message}] + state["messages"]
    print(f"final_prompt:{final_prompt}")
    return final_prompt


agent = create_react_agent(
    model=model_gpt,
    tools=[get_weather],
    prompt=prompt,
    response_format=ResponseAnswer,
)
response = agent.invoke(
    {"messages": [{"role": "user", "content": "what is the weather in Hà Nội"}]},
    config={"configurable": {"user_name": "Duong Tran"}, "recursion_limit": 5},
)
print(f"response: {response["messages"]}")
