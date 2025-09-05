# --- 若在 Colab，先安裝需要的套件（本機已安裝可略過）---
## !pip -qU install langgraph langchain langchain-ollama

# =========================
# 撰寫大腦主程式 (main.py) - 萬事俱備
# =========================

import asyncio
from contextlib import asynccontextmanager
from typing import TypedDict
from typing_extensions import Annotated

# LangChain / 模型與提示
from langchain_ollama import ChatOllama
from langchain.prompts import ChatPromptTemplate

# LangGraph
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# MCP 多伺服器客戶端
from langchain_mcp_adapters.client import MultiServerMCPClient


# ---- 1. 載入本地的 Ollama 模型 ----
# 請先在你的環境中確保已安裝並啟動 Ollama，且已下載 qwen3:4b：
#    ollama pull qwen3:4b
model = ChatOllama(model="qwen3:4b")  # 請確保你已下載此模型

# ---- 2. 設計一個提示語模板 (Prompt Template) ----
prompt = ChatPromptTemplate.from_template(
    "你是個擅長回答問題的助理。必要時，你可以呼叫外部工具來輔助回答。"
    "如果不知道答案，就說不知道。請用中文回答。\n\n問題：{question}"
)

# ---- 3. 定義 LangGraph 的狀態 (State) ----
class State(TypedDict):
    # messages 欄位會用來存放所有的對話紀錄
    messages: Annotated[list, add_messages]


# =========================
# 串連工具與大腦 - 建立 Graph
# =========================

# 建立一個函式來載入 MCP 工具
@asynccontextmanager
async def load_mcp_tools():
    """
    連線多個 MCP 伺服器並取得工具清單。
    - math 以 stdio 啟動：會自行啟動 mcp_servers/math.py
    - weather 以 streamable_http 連到 http://localhost:8001/sse
      （請先啟動你的 Weather MCP 伺服器）
    """
    async with MultiServerMCPClient({
        "math": {
            "command": "python",
            "args": ["mcp_servers/math.py"],
            "transport": "stdio",
        },
        "weather": {
            "url": "http://localhost:8001/sse",
            "transport": "streamable_http",
        },
    }) as client:
        yield client.get_tools()


# 建立 Graph 的主要函式
@asynccontextmanager
async def create_graph():
    """建立、組裝並回傳一個可以執行的 LangGraph 圖"""
    async with load_mcp_tools() as tools:
        print(f"成功載入的 MCP 工具：{[tool.name for tool in tools]}")

        # 將模型和工具綁定在一起（使模型可直接提出 tool_calls）
        llm_with_tool = model.bind_tools(tools)

        # --- 定義 Agent 節點的行為 ---
        def agent(state: State):
            messages = state["messages"]

            # 取出最後一則使用者訊息內容，灌入提示模板（system/context）
            # 並將模板訊息放在最前面，以維持 system -> user -> assistant 的常見順序
            last_user = None
            for m in reversed(messages):
                # 支援 tuple 形式或 BaseMessage（LangChain）
                if isinstance(m, tuple) and m and m[0] in ("user", "human"):
                    last_user = m[1]
                    break
                # BaseMessage 物件
                role = getattr(m, "type", None)
                if role in ("human", "user"):
                    last_user = getattr(m, "content", None)
                    break

            system_msgs = prompt.format_messages(question=last_user or "")
            full_msgs = list(system_msgs) + list(messages)

            # 呼叫可用工具的模型
            response = llm_with_tool.invoke(full_msgs)
            return {"messages": [response]}

        # --- 開始建構 Graph ---
        graph_builder = StateGraph(State)

        # 新增節點 (Node)
        graph_builder.add_node("agent", agent)
        graph_builder.add_node("tool", ToolNode(tools))

        # 設定流程的起點
        graph_builder.add_edge(START, "agent")

        # 由 Agent 的輸出決定是否需要走工具；若無工具呼叫則直接 END
        graph_builder.add_conditional_edges(
            "agent",
            tools_condition,
            {"tools": "tool", END: END},
        )

        # 工具執行完回到 Agent（可形成多輪：工具 -> Agent -> 工具 ...）
        graph_builder.add_edge("tool", "agent")

        # 編譯 Graph 並交回
        yield graph_builder.compile()

# =========================
# 來跟我們的 AI 助理聊天吧！
# =========================

async def main():
    """主程式進入點"""
    # 建立並取得我們編譯好的 Graph
    async with create_graph() as graph:
        # --- 測試案例 1: 查詢天氣 ---
        print("\n--- 測試天氣工具 ---")
        result = await graph.ainvoke({"messages": [("user", "高雄天氣怎麼樣")]})
        print(f"AI回覆：{result['messages'][-1].content}")

        # --- 測試案例 2: 數學計算 ---
        print("\n--- 測試數學工具 ---")
        result = await graph.ainvoke({"messages": [("user", "(3+5)x12等於多少")]})
        print(f"AI回覆：{result['messages'][-1].content}")


if __name__ == "__main__":
    # 執行主程式
    asyncio.run(main())