# import psycopg2

from openai import OpenAI
import uuid
from datetime import datetime
import sqlite3
import os

# OpenAI客户端配置
client = OpenAI(
    api_key="xai-xxx",
    base_url="https://api.x.ai/v1",
)

# 从环境变量获取数据库路径
DB_PATH = os.environ.get("DB_PATH", "chat.db")

def init_database():
    """初始化数据库，创建必要的表"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                model TEXT,
                token_usage INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def get_db_connection():
    """创建SQLite数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    return conn

def get_conversation_history(cursor, session_id, limit=100):
    """获取历史对话记录"""
    cursor.execute(
        "SELECT role, content FROM chat_sessions WHERE session_id=? AND role != 'system' ORDER BY timestamp ASC LIMIT ?",
        (session_id, limit)
    )
    messages = [{"role": row[0], "content": row[1]} for row in cursor.fetchall()]
    return messages

def save_message(cursor, session_id, role, content, model=None, token_usage=None):
    """保存对话消息到数据库"""
    cursor.execute(
        "INSERT INTO chat_sessions (session_id, role, content, model, token_usage) VALUES (?, ?, ?, ?, ?)",
        (session_id, role, content, model, token_usage)
    )

def get_ai_response(conversation):
    """获取AI的流式响应"""
    # 添加系统提示
    system_message = {
        "role": "system",
        "content": "你是一个专业、友好和富有同理心的AI助手。你会：\n1. 提供准确和有见地的回答\n2. 保持对话的连贯性和上下文\n3. 在必要时承认知识的局限性\n4. 以礼貌和专业的方式交流"
    }
    
    # 确保系统提示始终在对话开始
    if not conversation or conversation[0].get("role") != "system":
        full_conversation = [system_message] + conversation
    else:
        full_conversation = conversation

    stream = client.chat.completions.create(
        model="grok-2-latest",
        messages=full_conversation,
        stream=True
    )
    
    assistant_response = ""
    last_chunk = None
    
    for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)  # 逐步输出
            assistant_response += content
        last_chunk = chunk
    
    # 使用最后一个chunk来获取模型信息
    assistant_model = last_chunk.model
    
    # 在流式响应中，usage信息可能只在最后一个chunk中可用
    assistant_usage = getattr(last_chunk, 'usage', None)
    if assistant_usage:
        assistant_usage = assistant_usage.total_tokens
    else:
        # 如果在流式响应中无法获取usage，可以估算或使用默认值
        assistant_usage = len(assistant_response.split()) * 2  # 粗略估计
    
    return assistant_response, assistant_model, assistant_usage

def chat_with_openapi(session_id, user_input):
    """处理用户输入并返回AI响应"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            # 获取对话历史
            conversation = get_conversation_history(cursor, session_id)
            conversation.append({"role": "user", "content": user_input})
            
            # 保存用户消息
            save_message(cursor, session_id, "user", user_input)
            
            # 获取AI响应
            assistant_response, assistant_model, assistant_usage = get_ai_response(conversation)
            
            # 保存AI响应（包含模型信息和token使用量）
            save_message(cursor, session_id, "assistant", assistant_response, assistant_model, assistant_usage)
            
            conn.commit()
            return assistant_response, assistant_model, assistant_usage

        except Exception as e:
            conn.rollback()
            print(f"错误: {str(e)}")
            raise e

def generate_session_id():
    """生成唯一的会话ID"""
    # 使用时间戳前缀，方便按时间排序和查询
    timestamp = datetime.now().strftime("%Y%m%d")
    # 生成短UUID（取前8位即可）
    short_uuid = str(uuid.uuid4())[:8]
    return f"{timestamp}_{short_uuid}"

def main():
    """主函数：循环处理用户输入，直到用户按下 Ctrl+C 终止"""
    # 确保数据库和表已创建
    init_database()
    
    session_id = generate_session_id()
    print(f"\n欢迎使用AI助手！(按 Ctrl+C 可以退出)")
    print(f"会话ID: {session_id}")
    print("="*50)
    
    try:
        while True:
            try:
                user_input = input("\nUser: ").strip()
                if not user_input:  # 跳过空输入
                    continue
                    
                print("\nAssistant: ", end="")
                response, model, usage = chat_with_openapi(session_id, user_input)
                print()  # 打印空行
                print(f"Token使用量: {usage}")
                print("\n" + "-"*30)
                # print("继续对话请直接输入，按 Ctrl+C 结束对话")
                # print("-"*30)
                
            except Exception as e:
                print(f"\n对话出错: {str(e)}")
                print("让我们开始新的对话...")
                continue
                
    except KeyboardInterrupt:
        print("\n\n感谢使用！再见！")
        print("="*50)

if __name__ == "__main__":
    main()