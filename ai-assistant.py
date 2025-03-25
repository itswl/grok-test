import os
from openai import OpenAI
from mem0 import Memory
import logging
from datetime import datetime

# 前置操作
'''
1. 安装依赖
pip install openai mem0

2. 安装ollama
brew install ollama 

3. 下载模型
ollama pull nomic-embed-text:latest

4. 启动ollama # 不用启动
#  ollama run nomic-embed-text:latest

5. 启动qdrant
docker run -d -p 6333:6333 -p 6334:6334 -v $(pwd)/qdrant_storage:/qdrant/storage  qdrant/qdrant

'''

# ===================== 配置部分 =====================

# 系统提示词配置
SYSTEM_PROMPT = {
    "role": "system",
    "content": "你是一个专业的助手，可以提供专业的建议和帮助。"
               "你会记住用户的喜好和之前的对话内容，提供个性化的服务。"
}

# API配置
API_CONFIG = {
    "api_key": "xai-xxx",
    "base_url": "https://api.x.ai/v1",
    "model": "grok-2-latest",
    "temperature": 0.1,
    "max_tokens": 2000
}

# 存储配置
STORAGE_CONFIG = {
    "base_collection_name": "assistant_memory",  # 基础collection名称
    "vector_store": {
        "host": "localhost",
        "port": 6333,
        "embedding_model_dims": 768,
    },
    "embedder": {
        "model": "nomic-embed-text:latest",
        "ollama_base_url": "http://localhost:11434",
        "embedding_size": 768,
    }
}

def get_vector_store_config(user_id):
    """根据用户ID生成向量存储配置"""
    return {
        "llm": {
            "provider": "xai",
            "config": {
                "model": API_CONFIG["model"],
                "temperature": API_CONFIG["temperature"],
                "max_tokens": API_CONFIG["max_tokens"],
            }
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": f"{STORAGE_CONFIG['base_collection_name']}_{user_id}",
                "host": STORAGE_CONFIG["vector_store"]["host"],
                "port": STORAGE_CONFIG["vector_store"]["port"],
                "embedding_model_dims": STORAGE_CONFIG["vector_store"]["embedding_model_dims"],
            }
        },
        "embedder": {
            "provider": "ollama",
            "config": {
                "model": STORAGE_CONFIG["embedder"]["model"],
                "ollama_base_url": STORAGE_CONFIG["embedder"]["ollama_base_url"]
            },
        },
    }

# 命令配置
COMMANDS = {
    "summary": {
        "command": "/summary",
        "description": "生成对话总结"
    },
    "memories": {
        "command": "/memories",
        "description": "查看记忆"
    },
    "history": {
        "command": "/history",
        "description": "查看带时间戳的记忆历史"
    },
    "update": {
        "command": "/update <id> <内容>",
        "description": "更新指定ID的记忆"
    },
    "delete": {
        "command": "/delete <id>",
        "description": "删除指定ID的记忆"
    },
    "reset": {
        "command": "/reset",
        "description": "重置所有记忆"
    },
    "debug": {
        "command": "/debug",
        "description": "显示调试信息"
    },
    "exit": {
        "command": "/exit",
        "description": "退出程序"
    }
}

# 日志配置
LOGGING_CONFIG = {
    "default_level": logging.ERROR,
    "disabled_loggers": ['mem0', 'qdrant_client']
}

# ===================== 日志初始化 =====================

# 设置日志级别
logging.getLogger().setLevel(LOGGING_CONFIG["default_level"])
# 禁用特定库的日志
for logger in LOGGING_CONFIG["disabled_loggers"]:
    logging.getLogger(logger).setLevel(logging.ERROR)

# 设置环境变量
os.environ["XAI_API_KEY"] = API_CONFIG["api_key"]

# API客户端配置
api_key = API_CONFIG["api_key"]
base_url = API_CONFIG["base_url"]

class PersonalTravelAssistant:
    def __init__(self, user_id):
        """初始化个人助手"""
        # 先初始化所有基本属性，确保即使出错也能使用
        self.memory_store = {}
        self.use_memory = False
        self.user_id = user_id
        # 初始化消息历史
        self.messages = [SYSTEM_PROMPT]
        
        try:
            # 创建OpenAI客户端
            self.client = OpenAI(
                api_key=API_CONFIG["api_key"],
                base_url=API_CONFIG["base_url"],
            )
            
            # 获取用户特定的向量存储配置
            vector_config = get_vector_store_config(user_id)
            
            # 初始化mem0记忆系统
            self.memory = Memory.from_config(vector_config)
            self.use_memory = True
            print(f"成功初始化mem0记忆系统 (使用向量数据库)")
            print(f"记忆存储位置: {vector_config['vector_store']['config']['collection_name']}")
            
        except Exception as e:
            error_msg = str(e)
            print(f"初始化mem0失败: {error_msg}")
            self._handle_initialization_error(error_msg)
    
    def _handle_initialization_error(self, error_msg):
        """处理初始化错误"""
        if "Qdrant" in error_msg:
            print("\n错误原因: Qdrant向量数据库初始化失败")
            print("请检查Qdrant服务是否正在运行，默认端口是否为6333")
        elif "Ollama" in error_msg:
            print("\n错误原因: Ollama嵌入服务初始化失败")
            print("请检查:")
            print("1. Ollama服务是否正在运行")
            print("2. 是否已下载nomic-embed-text模型")
            print("3. 服务地址是否正确(默认: http://localhost:11434)")
        
        self.use_memory = False
        # 继续使用简单内存存储和基本会话历史
    

    def ask_question(self, question, user_id):
        """处理用户问题并返回回答"""
        try:
            # 获取相关记忆
            related_memories = self.search_memories(question, user_id=user_id)
            
            # 构建带有记忆上下文的提示
            if related_memories:
                memory_context = "\n".join([f"- {mem}" for mem in related_memories])
                prompt = f"用户问题: {question}\n\n以下是与该问题相关的历史信息:\n{memory_context}"
            else:
                prompt = question
                
            # 添加用户消息
            self.messages.append({"role": "user", "content": prompt})
            
            # 生成回答
            # logging.info(f"向模型发送请求，消息数量: {len(self.messages)}")
            # print('xxxxxx',self.messages)
            response = self.client.chat.completions.create(
                model="grok-2-latest",
                messages=self.messages,
                stream=True  # 启用流式输出
            )
            
            answer = ""
            for chunk in response:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    print(content, end="", flush=True)  # 直接打印内容
                    answer += content
            
            # 添加助手回答到历史
            self.messages.append({"role": "assistant", "content": answer})
            
            # 控制消息历史长度，保留最近10条
            if len(self.messages) > 12:  # 系统消息+10条对话(5问5答)
                self.messages = [self.messages[0]] + self.messages[-10:]
            
            # 存储到记忆系统
            self.add_memory(question, user_id)
            self.add_memory(answer, user_id, is_assistant=True)
            
            return answer
            
        except Exception as e:
            # logging.error(f"处理问题时出错: {str(e)}")
            return f"抱歉，处理您的问题时出现错误: {str(e)}"
    
    def add_memory(self, content, user_id, is_assistant=False):
        """将内容添加到记忆系统"""
        try:
            if self.use_memory:
                role = "assistant" if is_assistant else "user"
                # 修改为使用适合mem0的格式
                message = [{"role": role, "content": content}]
                # print(message)
                # 确保添加到记忆
                try:
                    # 添加错误处理以捕获XAI API不兼容问题
                    try:
                        result = self.memory.add(message, user_id=user_id, metadata={"role": role, "timestamp": datetime.now().isoformat()})
                        # 调试信息
                        print(f"记忆添加成功: [角色: {role}] - {content[:30]}..." if len(content) > 30 else f"记忆添加成功: [角色: {role}] - {content}")
                    except TypeError as api_error:
                        if "tools" in str(api_error) and "XAILLM" in str(api_error):
                            # XAI API不兼容问题，回退到简单存储
                            raise Exception("XAI API不兼容，使用简单内存存储")
                        else:
                            raise api_error
                except Exception as mem_error:
                    print(f"记忆添加失败: {str(mem_error)}")
                    # 回退到简单存储
                    if user_id not in self.memory_store:
                        self.memory_store[user_id] = []
                    
                    self.memory_store[user_id].append({
                        "role": role,
                        "content": content,
                        "timestamp": datetime.now().isoformat()
                    })
            else:
                # 使用简单的内存存储
                if user_id not in self.memory_store:
                    self.memory_store[user_id] = []
                
                self.memory_store[user_id].append({
                    "role": "assistant" if is_assistant else "user",
                    "content": content,
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            print(f"添加记忆时出错: {str(e)}")
            # 确保即使出错也能记录到内存存储中
            if user_id not in self.memory_store:
                self.memory_store[user_id] = []
            
            self.memory_store[user_id].append({
                "role": "assistant" if is_assistant else "user",
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
    
    def get_all_memories(self, user_id):
        """获取指定用户的所有记忆"""
        try:
            if self.use_memory:
                memories = self.memory.get_all(user_id=user_id)
                # 处理返回结果的结构，适应mem0的API变化
                result_list = []
                if isinstance(memories, dict) and 'results' in memories:
                    for mem in memories['results']:
                        if isinstance(mem, dict) and 'text' in mem:
                            result_list.append(mem['text'])
                        elif isinstance(mem, dict) and 'memory' in mem:
                            result_list.append(mem['memory'])
                        else:
                            # 尝试将整个对象转换为字符串
                            result_list.append(str(mem))
                elif isinstance(memories, list):
                    for mem in memories:
                        if isinstance(mem, dict):
                            if 'text' in mem:
                                result_list.append(mem['text'])
                            elif 'memory' in mem:
                                result_list.append(mem['memory'])
                            else:
                                # 将字典内容格式化为字符串
                                result_list.append(str(mem))
                        else:
                            result_list.append(str(mem))
                
                return result_list
            else:
                if user_id not in self.memory_store:
                    return []
                
                return [f"[{mem['role']}]: {mem['content']}" for mem in self.memory_store[user_id]]
                
        except Exception as e:
            # logging.error(f"获取记忆时出错: {str(e)}")
            return []
    
    def search_memories(self, query, user_id, limit=5):
        """搜索与查询相关的记忆"""
        try:
            if self.use_memory:
                memories = self.memory.search(query=query, user_id=user_id, limit=limit)
                # 处理返回结果的结构，适应mem0的API变化
                result_list = []
                if isinstance(memories, dict) and 'results' in memories:
                    for mem in memories['results']:
                        if isinstance(mem, dict) and 'text' in mem:
                            result_list.append(mem['text'])
                        elif isinstance(mem, dict) and 'memory' in mem:
                            result_list.append(mem['memory'])
                        else:
                            # 尝试将整个对象转换为字符串
                            result_list.append(str(mem))
                elif isinstance(memories, list):
                    for mem in memories:
                        if isinstance(mem, dict):
                            if 'text' in mem:
                                result_list.append(mem['text']) 
                            elif 'memory' in mem:
                                result_list.append(mem['memory'])
                            else:
                                # 尝试字典中的所有字段
                                result_list.append(str(mem))
                        else:
                            result_list.append(str(mem))
                
                return result_list
            else:
                # 简单的相似度查询实现
                if user_id not in self.memory_store or not self.memory_store[user_id]:
                    return []
                
                # 简单按时间返回最近的几条消息
                recent_msgs = self.memory_store[user_id][-limit:]
                return [f"{msg['content']}" for msg in recent_msgs]
                
        except Exception as e:
            # logging.error(f"搜索记忆时出错: {str(e)}")
            return []
    
    def generate_summary(self, user_id):
        """为用户的对话生成总结"""
        # 获取所有记忆
        memories = self.get_all_memories(user_id)
        
        # 优先使用内存存储中的记忆，如果内存存储也没有记忆，就使用会话历史
        if len(memories) < 2 and hasattr(self, 'memory_store') and user_id in self.memory_store:
            memories = [f"[{mem['role']}]: {mem['content']}" for mem in self.memory_store[user_id]]
        
        # 如果记忆仍然不足，使用会话历史
        if len(memories) < 2 and len(self.messages) > 1:
            # 从会话历史中提取对话内容，跳过系统消息
            memories = []
            for i in range(1, len(self.messages)):
                msg = self.messages[i]
                memories.append(f"[{msg['role']}]: {msg['content']}")
        
        # 检查是否有足够的内容生成总结
        if len(memories) < 2:  # 修改为至少需要2条记忆
            return "对话太短，无需总结。"
        
        try:
            # 构建总结提示
            summary_prompt = f"请总结以下旅行相关对话的主要内容（100-200字）：\n\n{memories}"
            
            # 请求模型生成总结
            response = self.client.chat.completions.create(
                model="grok-2-latest",
                messages=[{"role": "user", "content": summary_prompt}],
                temperature=0.5,
                max_tokens=300
            )
            
            summary = response.choices[0].message.content
            
            # 将总结添加到记忆
            self.add_memory(f"对话总结: {summary}", user_id, is_assistant=True)
            
            return summary
            
        except Exception as e:
            error_msg = str(e)
            print(f"生成总结时出错: {error_msg}")
            
            # 尝试使用简单总结方法
            try:
                # 提取关键词和主题
                all_content = " ".join(memories)
                simple_summary = f"讨论了关于{all_content[:100]}...等话题。"
                return simple_summary
            except:
                return f"生成总结时出错: {error_msg}"

    def update_memory(self, memory_id, new_content, user_id):
        """更新指定ID的记忆内容"""
        try:
            if self.use_memory:
                # 获取所有记忆
                memories = self.memory.get_all(user_id=user_id)
                
                # 检查记忆ID是否有效
                if not isinstance(memories, dict) or 'results' not in memories or len(memories['results']) <= memory_id - 1:
                    return f"无效的记忆ID: {memory_id}"
                
                # 获取记忆的唯一标识符（内部ID）
                memory_item = memories['results'][memory_id - 1]
                if 'id' not in memory_item:
                    return "无法更新记忆，缺少内部ID"
                
                internal_id = memory_item['id']
                
                # 更新记忆
                self.memory.update(
                    memory_id=internal_id,
                    memory=[{"role": "user", "content": new_content}]
                )
                
                return f"已更新记忆 #{memory_id}"
            else:
                # 简单内存存储的实现
                if user_id not in self.memory_store or len(self.memory_store[user_id]) < memory_id:
                    return f"无效的记忆ID: {memory_id}"
                
                # 更新记忆
                self.memory_store[user_id][memory_id - 1]["content"] = new_content
                self.memory_store[user_id][memory_id - 1]["timestamp"] = datetime.now().isoformat()
                
                return f"已更新记忆 #{memory_id}"
                
        except Exception as e:
            return f"更新记忆时出错: {str(e)}"
    
    def delete_memory(self, memory_id, user_id):
        """删除指定ID的记忆"""
        try:
            if self.use_memory:
                # 获取所有记忆
                memories = self.memory.get_all(user_id=user_id)
                
                # 检查记忆ID是否有效
                if not isinstance(memories, dict) or 'results' not in memories or len(memories['results']) <= memory_id - 1:
                    return f"无效的记忆ID: {memory_id}"
                
                # 获取记忆的唯一标识符（内部ID）
                memory_item = memories['results'][memory_id - 1]
                if 'id' not in memory_item:
                    return "无法删除记忆，缺少内部ID"
                
                internal_id = memory_item['id']
                
                # 删除记忆
                self.memory.delete(memory_id=internal_id)
                
                return f"已删除记忆 #{memory_id}"
            else:
                # 简单内存存储的实现
                if user_id not in self.memory_store or len(self.memory_store[user_id]) < memory_id:
                    return f"无效的记忆ID: {memory_id}"
                
                # 删除记忆
                del self.memory_store[user_id][memory_id - 1]
                
                return f"已删除记忆 #{memory_id}"
                
        except Exception as e:
            return f"删除记忆时出错: {str(e)}"
    
    def get_memory_history(self, user_id, limit=10):
        """获取用户的记忆历史，带有时间戳和ID"""
        try:
            if self.use_memory:
                memories = self.memory.get_all(user_id=user_id)
                
                result_list = []
                if isinstance(memories, dict) and 'results' in memories:
                    for i, mem in enumerate(memories['results'], 1):
                        if isinstance(mem, dict):
                            timestamp = mem.get('timestamp', 'N/A')
                            if 'text' in mem:
                                result_list.append((i, timestamp, mem['text']))
                            elif 'memory' in mem:
                                result_list.append((i, timestamp, mem['memory']))
                            else:
                                result_list.append((i, timestamp, str(mem)))
                
                # 最多返回limit条记录
                return result_list[-limit:]
            else:
                if user_id not in self.memory_store:
                    return []
                
                result_list = []
                for i, mem in enumerate(self.memory_store[user_id], 1):
                    timestamp = mem.get('timestamp', 'N/A')
                    result_list.append((i, timestamp, mem['content']))
                
                # 最多返回limit条记录
                return result_list[-limit:]
                
        except Exception as e:
            return [(0, 'ERROR', f"获取记忆历史时出错: {str(e)}")]
    
    def reset_memories(self, user_id):
        """重置用户的所有记忆"""
        try:
            if self.use_memory:
                # 获取所有记忆
                memories = self.memory.get_all(user_id=user_id)
                
                deleted_count = 0
                if isinstance(memories, dict) and 'results' in memories:
                    for mem in memories['results']:
                        if isinstance(mem, dict) and 'id' in mem:
                            self.memory.delete(memory_id=mem['id'])
                            deleted_count += 1
                
                return f"已重置 {deleted_count} 条记忆"
            else:
                # 简单内存存储的实现
                if user_id in self.memory_store:
                    deleted_count = len(self.memory_store[user_id])
                    self.memory_store[user_id] = []
                    return f"已重置 {deleted_count} 条记忆"
                else:
                    return "没有记忆需要重置"
                
        except Exception as e:
            return f"重置记忆时出错: {str(e)}"

def handle_command(command, assistant, user_id, conversation_history):
    """处理命令输入"""
    if command.lower() in ["exit", "q", "/exit", "/quit"]:
        return True, None  # 返回退出标志
        
    command_handlers = {
        COMMANDS["summary"]["command"]: lambda: handle_summary_command(assistant, user_id),
        COMMANDS["memories"]["command"]: lambda: handle_memories_command(assistant, user_id),
        COMMANDS["history"]["command"]: lambda: handle_history_command(assistant, user_id),
        COMMANDS["reset"]["command"]: lambda: handle_reset_command(assistant, user_id),
        COMMANDS["debug"]["command"]: lambda: handle_debug_command(assistant, user_id)
    }
    
    # 处理基本命令
    if command.lower() in command_handlers:
        command_handlers[command.lower()]()
        return False, True
    
    # 处理需要参数的命令
    if command.lower().startswith(COMMANDS["delete"]["command"].split()[0]):
        handle_delete_command(command, assistant, user_id)
        return False, True
    elif command.lower().startswith(COMMANDS["update"]["command"].split()[0]):
        handle_update_command(command, assistant, user_id)
        return False, True
        
    return False, False  # 不是命令

def handle_summary_command(assistant, user_id):
    """处理总结命令"""
    print("\n生成对话总结中...")
    summary = assistant.generate_summary(user_id)
    print(f"\n对话总结：\n{summary}")
    print("\n" + "-"*50)

def handle_memories_command(assistant, user_id):
    """处理查看记忆命令"""
    memories = assistant.get_all_memories(user_id)
    print("\n当前记忆:")
    for i, memory in enumerate(memories, 1):
        print(f"{i}. {memory}")
    print("\n" + "-"*50)

def handle_history_command(assistant, user_id):
    """处理历史记录命令"""
    print("\n记忆历史:")
    history = assistant.get_memory_history(user_id)
    for mem_id, timestamp, content in history:
        print(f"ID: {mem_id} | 时间: {timestamp}")
        print(f"内容: {content}")
        print("-"*30)
    print("\n" + "-"*50)

def handle_reset_command(assistant, user_id):
    """处理重置命令"""
    print("\n重置记忆...")
    result = assistant.reset_memories(user_id)
    print(result)
    print("\n" + "-"*50)

def handle_debug_command(assistant, user_id):
    """处理调试命令"""
    print("\n调试信息:")
    print(f"记忆系统工作状态: {assistant.use_memory}")
    print(f"当前会话历史长度: {len(assistant.messages)}")
    if hasattr(assistant, 'memory_store') and user_id in assistant.memory_store:
        print(f"内存记忆存储条数: {len(assistant.memory_store[user_id])}")
    print("\n" + "-"*50)

def handle_delete_command(command, assistant, user_id):
    """处理删除命令"""
    try:
        parts = command.split(" ", 1)
        if len(parts) < 2:
            print("格式错误，请使用", COMMANDS["delete"]["command"])
            return
        
        memory_id = int(parts[1].strip())
        result = assistant.delete_memory(memory_id, user_id)
        print(result)
    except ValueError:
        print("无效的ID，请输入数字")
    except Exception as e:
        print(f"处理删除命令时出错: {str(e)}")
    print("\n" + "-"*50)

def handle_update_command(command, assistant, user_id):
    """处理更新命令"""
    try:
        parts = command.split(" ", 2)
        if len(parts) < 3:
            print("格式错误，请使用", COMMANDS["update"]["command"])
            return
        
        memory_id = int(parts[1].strip())
        new_content = parts[2].strip()
        result = assistant.update_memory(memory_id, new_content, user_id)
        print(result)
    except ValueError:
        print("无效的ID，请输入数字")
    except Exception as e:
        print(f"处理更新命令时出错: {str(e)}")
    print("\n" + "-"*50)

def handle_exit(assistant, user_id, conversation_history):
    """处理退出逻辑"""
    if len(conversation_history) >= 6:
        try:
            print("\n生成对话总结中...")
            summary = assistant.generate_summary(user_id)
            print(f"\n对话总结：\n{summary}")
        except Exception as e:
            print(f"\n生成总结时出错: {str(e)}")
    else:
        print("对话长度小于6，不生成总结")
    
    print("="*50)
    print("感谢使用智能助手！再见！")

def main():
    """主函数：处理用户输入并展示响应"""
    try:
        # 使用固定用户ID，方便测试
        user_id = "user_123"
        
        # 创建助手实例，传入用户ID
        assistant = PersonalTravelAssistant(user_id)
        
        print("\n欢迎使用智能助手！(输入 'exit' 或 'q' 退出)")
        print(f"用户ID: {user_id}")
        print(f"记忆系统: {'向量数据库' if assistant.use_memory else '简单内存存储'}")
        print("="*50)
        print("可用命令:")
        for cmd in COMMANDS.values():
            print(f"{cmd['command']} - {cmd['description']}")
        print("-"*50)
        
        # 记录对话历史以备失败时使用
        conversation_history = []
        
        while True:
            try:
                # 获取用户输入
                user_input = input("\n问题: ").strip()
                if not user_input:  # 跳过空输入
                    continue
                
                # 处理命令
                should_exit, is_command = handle_command(user_input, assistant, user_id, conversation_history)
                
                if should_exit:
                    handle_exit(assistant, user_id, conversation_history)
                    break
                
                if is_command:
                    continue
                
                # 处理普通对话
                conversation_history.append({"role": "user", "content": user_input})
                print("\n助手: ", end="", flush=True)
                answer = assistant.ask_question(user_input, user_id)
                print()  # 添加换行
                conversation_history.append({"role": "assistant", "content": answer})
                print("\n" + "-"*50)
                
            except KeyboardInterrupt:
                handle_exit(assistant, user_id, conversation_history)
                break
            except Exception as e:
                print(f"\n处理输入时出错: {str(e)}")
                print("请重试或输入其他命令")
                continue
            
    except Exception as e:
        print(f"\n程序启动出错: {str(e)}")
        return

if __name__ == "__main__":
    main() 