import os
import json
from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

SYSTEM_PROMPT = "你是一个待办事项助理。当用户想要添加、查看、标记完成或删除待办事项时，请调用相应的工具；如果是普通聊天，直接回答即可。不要编造工具的执行结果。"

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
                tools=tools_schema
            )
            msg = resp.choices[0].message
            
            if not msg.tool_calls:
                return msg.content

            messages.append(msg)
            
            for call in msg.tool_calls:
                result = await session.call_tool(
                    call.function.name, 
                    json.loads(call.function.arguments)
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": result.content[0].text,
                })
                
            final = client.chat.completions.create(
                model="deepseek-chat", 
                messages=messages
            )
            return final.choices[0].message.content
