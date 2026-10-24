import os
import json
import re
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = "你是一个待办事项助理。请直接调用工具。"

async def run_agent(user_input: str, history: list[dict]) -> str:
    server_params = StdioServerParameters(command="python", args=["mcp_server.py"])
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            tools = await session.list_tools()
            tools_schema = [{
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.input_schema,
                },
            } for t in tools.tools]

            messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
                {"role": "user", "content": user_input}
            ]
            
            resp = client.chat.completions.create(
                model="deepseek-chat", 
                messages=messages, 
                tools=tools_schema,
                temperature=0.0 
            )
            msg = resp.choices[0].message

            # 如果模型正常发起了工具调用
            if msg.tool_calls:
                reply_text = ""
                for call in msg.tool_calls:
                    result = await session.call_tool(
                        call.function.name, 
                        json.loads(call.function.arguments)
                    )
                    reply_text += result.content[0].text + "\n"
                # 直接把工具的真实结果告诉用户
                return reply_text.strip()

            # 如果模型没发起工具调用，但输出了底层乱码
            if msg.content and "DSML" in msg.content:
                # 暴力用正则提取要删除，完成的数字ID
                match = re.search(r'name="(?:id|todo_id)"[^>]*>(\d+)<', msg.content)
                if match:
                    todo_id = int(match.group(1))
                    if "delete_todo" in msg.content:
                        result = await session.call_tool("delete_todo", {"id": todo_id})
                        return f"（系统自动修复）{result.content[0].text}"
                    elif "complete_todo" in msg.content:
                        result = await session.call_tool("complete_todo", {"id": todo_id})
                        return f"（系统自动修复）{result.content[0].text}"
                return "抱歉，系统无法解析该操作，请重试。"

            # 3. 普通聊天（没有任何工具调用），直接返回大模型的回答
            return msg.content if msg.content else "抱歉，我没有理解你的意思。"
