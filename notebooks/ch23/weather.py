from mcp.server.fastmcp import FastMCP

# 建立一個名為 Weather 的 MCP server，指定 HTTP 監聽埠號
mcp = FastMCP("Weather", port=8001)

@mcp.tool()
async def get_weather(location: str) -> str:
    """查詢指定地點的天氣"""
    # 在這裡你可以改成實際 API 呼叫，例如 open-meteo 或中央氣象局
    return f"{location} 的天氣總是飽和度很高"

if __name__ == "__main__":
    # 啟動 MCP 伺服器，使用 streamable-http 作為傳輸
    mcp.run(transport="streamable-http")
