import uuid
import requests
import time

# Agent 服务地址
AGENT_SERVER_URL = "http://192.168.77.102:8602/v1/chat/completions"

class AgentClient:
    """Agent 对话客户端"""
    def __init__(self):
        self.reset_session()

    def reset_session(self):
        """重置会话ID和记忆"""
        self.session_id = str(uuid.uuid4())
        self.memory_data = None
        print(f"🔄 会话重置: {self.session_id}")

    def chat(self, query):
        request_id = str(uuid.uuid4())
        payload = {
            "session_id": self.session_id,
            "request_id": request_id,
            "query": query,
            "voice": True,
            "memory_data": self.memory_data
        }
        
        try:
            print(f"🤔 思考中...")
            resp = requests.post(AGENT_SERVER_URL, json=payload, timeout=20.0)
            if resp.status_code == 200:
                res_data = resp.json()
                if res_data.get("response") == "【ERROR】":
                    return "抱歉，我遇到了一些问题。"
                
                self.memory_data = res_data.get("memory")
                return res_data.get("response", "")
            else:
                print(f"❌ Agent Error Status: {resp.status_code}")
                return "服务暂时不可用。"
        except Exception as e:
            print(f"❌ Agent Request Error: {e}")
            return "连接服务器失败。"