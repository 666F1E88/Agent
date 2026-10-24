import asyncio
import nest_asyncio
# 必须加这行，否则 Streamlit 运行异步代码会报错
nest_asyncio.apply() 

import streamlit as st
# 从队友的代码中导入后端的 run_agent 函数
from agent import run_agent 

st.set_page_config(page_title="智能待办助理", page_icon="✅", layout="centered")
st.title("✅ 智能待办清单助理")
st.caption("你可以这样对我说：'帮我记一个任务，明天交作业' 或 '我有哪些没做的任务？'")

# 初始化对话历史
if "messages" not in st.session_state:
    st.session_state.messages = []

# 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 侧边栏加个清空按钮
with st.sidebar:
    st.header("控制面板")
    if st.button("🗑️ 清空当前对话记忆"):
        st.session_state.messages = []
        st.rerun()

# 接收用户输入
prompt = st.chat_input("说点什么...")

if prompt:
    # 显示用户的输入
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用 A 的代码并显示回复
    with st.chat_message("assistant"):
        with st.spinner("思考并操作中..."):
            try:
                history = st.session_state.messages[:-1] 
                # 运行后端的异步函数
                reply = asyncio.run(run_agent(prompt, history))
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})

                # 如果检测到大模型的回复里有导出成功的字眼
                if "已成功导出" in reply or "todo_export.md" in reply:
                    try:
                        # 前端直接去读取当前文件夹下的 md 文件
                        with open("todo_export.md", "r", encoding="utf-8") as f:
                            md_content = f.read()
                        
                        # 渲染一个漂亮的下载按钮
                        st.download_button(
                            label="📥 点击这里下载 Markdown 文件",
                            data=md_content,
                            file_name="我的待办清单.md",
                            mime="text/markdown",
                            key="download_md"
                        )
                    except FileNotFoundError:
                        st.warning("提示：文件已生成，但前端未能成功读取到本地文件。")

            except Exception as e:
                st.error(f"出错了：{e}")