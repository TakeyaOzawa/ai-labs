import requests
import asyncio
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class AgentCommunicator:
    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.endpoints = {
            "planner": "http://planner-agent.ai-agents.svc.cluster.local:8080/mcp",
            "architect": "http://architect-agent.ai-agents.svc.cluster.local:8081/mcp", 
            "coder": "http://coder-agent.ai-agents.svc.cluster.local:8082/mcp",
            "tester": "http://tester-agent.ai-agents.svc.cluster.local:8083/mcp"
        }
    
    async def send_command(self, target_agent: str, command: str, payload: Dict[Any, Any]) -> Dict[Any, Any]:
        """エージェント間コマンド送信"""
        message = {
            "command": command,
            "sender": self.agent_name,
            "target": target_agent,
            "payload": payload,
            "callback_url": f"http://{self.agent_name.lower()}-agent.ai-agents.svc.cluster.local:{self._get_port()}/callback",
            "timeout": 30
        }
        
        try:
            response = requests.post(
                self.endpoints[target_agent.lower()], 
                json=message,
                timeout=30
            )
            logger.info(f"[{self.agent_name}] Sent {command} to {target_agent}")
            return response.json()
        except Exception as e:
            logger.error(f"[{self.agent_name}] Failed to send {command} to {target_agent}: {str(e)}")
            return {"error": str(e), "status": "failed"}
    
    def _get_port(self) -> int:
        port_map = {"planner": 8080, "architect": 8081, "coder": 8082, "tester": 8083}
        return port_map.get(self.agent_name.lower(), 8080)
