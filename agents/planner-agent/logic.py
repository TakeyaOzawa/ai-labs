from fastapi import FastAPI, Request
import json
import logging
import sys
import os

# 共通モジュールのパスを追加
sys.path.append('/app/common')
from agent_communicator import AgentCommunicator

app = FastAPI()
AGENT_NAME = "PlannerAgent"

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# エージェント通信クライアント
communicator = AgentCommunicator("Planner")

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """MCPエンドポイント: ユーザーからのタスクを受け取り、適切なエージェントに分解・指示"""
    data = await request.json()
    sender = data.get("sender", "User")
    command = data.get("command", "UNKNOWN")
    payload = data.get("payload", {})
    
    logger.info(f"[{AGENT_NAME}] Received {command} from {sender}")
    
    if command == "INITIAL_TASK":
        return await handle_initial_task(payload)
    elif command == "TASK_COMPLETE":
        return await handle_task_complete(payload)
    else:
        return {"status": "error", "message": f"Unknown command: {command}"}

async def handle_initial_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """初期タスクを受け取り、設計フェーズを開始"""
    requirements = payload.get("requirements", "")
    constraints = payload.get("constraints", [])
    
    logger.info(f"[{AGENT_NAME}] Processing initial task: {requirements}")
    
    # ArchitectAgentに設計を依頼
    design_request = await communicator.send_command("architect", "PLAN_TASK", {
        "task_id": f"design_{hash(requirements)}",
        "requirements": requirements,
        "constraints": constraints,
        "priority": "high"
    })
    
    return {
        "status": "task_initiated",
        "message": "タスクを開始し、設計フェーズに移行しました",
        "architect_response": design_request
    }

async def handle_task_complete(payload: Dict[str, Any]) -> Dict[str, Any]:
    """タスク完了報告を受け取り、ユーザーに報告"""
    task_id = payload.get("task_id", "")
    result = payload.get("result", "")
    artifacts = payload.get("artifacts", [])
    
    logger.info(f"[{AGENT_NAME}] Task {task_id} completed with result: {result}")
    
    return {
        "status": "project_completed",
        "message": "プロジェクトが正常に完了しました",
        "task_id": task_id,
        "result": result,
        "artifacts": artifacts
    }

@app.post("/callback")
async def handle_callback(request: Request):
    """他のエージェントからのコールバックを処理"""
    data = await request.json()
    logger.info(f"[{AGENT_NAME}] Received callback: {data}")
    return {"status": "callback_received"}

@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy", "agent": AGENT_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
