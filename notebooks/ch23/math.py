from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Math")

@mcp.tool()
def add(a: int, b: int) -> int:
    """計算兩個整數相加"""
    return a + b

@mcp.tool()
def multiply(a: int, b: int) -> int:
    """計算兩個整數相乘"""
    return a * b

if __name__ == "__main__":
    # 啟動 MCP 伺服器，並指定使用 stdio 方式連線
    mcp.run(transport="stdio")
