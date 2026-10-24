import os
import json
import re
import sys
import datetime
from openai import AsyncOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

client = AsyncOpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

async def run_agent(user_input: str, history: list[dict]) -> str:
    memory_text = ""
    if os.path.exists("user_memory.json"):
        with open("user_memory.json", "r", encoding="utf-8") as f:
            try:
                mem = json.load(f)
                memory_text = f"【用户档案】{json.dumps(mem, ensure_ascii=False)}。"
            except: pass

    now = datetime.datetime.now()
    time_str = now.strftime("%Y年%m月%d日 %H:%M:%S")

    SYSTEM_PROMPT = f"""你是一个极其专业的智能日程与待办管理助理。
当前真实时间是：{time_str}。请严格以此时间为基准计算“今天”、“明天”。
{memory_text}

【核心能力要求】
1. 自动化任务：添加任务时自动推理填入 priority(高/中/低)、duration(耗时)、deadline(截止时间)。
2. 日程规划：用户说“安排今天”时，先调 list_todos 查询，再结合当前真实时间和优先级，排出一个合理的时间表。
3. 记忆功能：如果用户告诉你称呼/习惯，请调用 save_memory。
4. 导出功能：调用 export_markdown 导出文件。
5. 严禁输出任何底层 XML/DSML 乱码。"""

    server_params = StdioServerParameters(command=sys.executable, args=["mcp_server.py"])
    
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
            
            resp = await client.chat.completions.create(
                model="deepseek-chat", 
                messages=messages, 
                tools=tools_schema,
                temperature=0.1 
            )
            msg = resp.choices[0].message

            # 正常工具调用
            if msg.tool_calls:
                reply_text = ""
                for call in msg.tool_calls:
                    result = await session.call_tool(
                        call.function.name, 
                        json.loads(call.function.arguments)
                    )
                    reply_text += result.content[0].text + "\n"
                
                if any(call.function.name in ["list_todos", "export_markdown"] for call in msg.tool_calls):
                    messages.append(msg)
                    for call in msg.tool_calls:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": reply_text,
                        })
                    final = await client.chat.completions.create(
                        model="deepseek-chat", 
                        messages=messages
                    )
                    return final.choices[0].message.content
                
                return reply_text.strip()

            # 暴力拦截，只要文本里有乱码，直接强制执行操作
            if msg.content and ("DSML" in msg.content or "invoke" in msg.content or "<|" in msg.content):
                # 暴力抓取乱码里的所有数字
                numbers = re.findall(r'\d+', msg.content)
                
                if "delete_todo" in msg.content and numbers:
                    # 通常参数里的ID在最后面，取最后一个数字作为ID
                    todo_id = int(numbers[-1])
                    result = await session.call_tool("delete_todo", {"id": todo_id})
                    return f"（系统自动修复）{result.content[0].text}"
                
                elif "complete_todo" in msg.content and numbers:
                    todo_id = int(numbers[-1])
                    result = await session.call_tool("complete_todo", {"id": todo_id})
                    return f"（系统自动修复）{result.content[0].text}"
                
                return "抱歉，系统拦截到未知乱码格式，请重新下达指令。"

            return msg.content if msg.content else "抱歉，我没有理解你的意思。"
