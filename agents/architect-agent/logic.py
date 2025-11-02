from fastapi import FastAPI, Request
import json
import logging
import sys
import os
from typing import Dict, Any

# 共通モジュールのパスを追加
sys.path.append('/app/common')
from agent_communicator import AgentCommunicator

app = FastAPI()
AGENT_NAME = "ArchitectAgent"

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# エージェント通信クライアント
communicator = AgentCommunicator("Architect")

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """MCPエンドポイント: 設計タスクを受け取り、技術仕様を生成"""
    data = await request.json()
    sender = data.get("sender", "Unknown")
    command = data.get("command", "UNKNOWN")
    payload = data.get("payload", {})
    
    logger.info(f"[{AGENT_NAME}] Received {command} from {sender}")
    
    if command == "PLAN_TASK":
        return await handle_plan_task(payload)
    else:
        return {"status": "error", "message": f"Unknown command: {command}"}

async def handle_plan_task(payload: Dict[str, Any]) -> Dict[str, Any]:
    """設計タスクを処理し、技術仕様を生成"""
    task_id = payload.get("task_id", "")
    requirements = payload.get("requirements", "")
    constraints = payload.get("constraints", [])
    
    logger.info(f"[{AGENT_NAME}] Processing design task: {task_id}")
    
    # 技術仕様を生成
    tech_stack = await generate_tech_stack(requirements, constraints)
    architecture = await generate_architecture(requirements)
    
    # CoderAgentにコード生成を依頼
    code_request = await communicator.send_command("coder", "CODE_REQUEST", {
        "task_id": task_id,
        "specifications": {
            "tech_stack": tech_stack,
            "architecture": architecture,
            "requirements": requirements
        },
        "files": await generate_file_list(requirements),
        "priority": "high"
    })
    
    return {
        "status": "design_completed",
        "message": "設計が完了し、コード生成フェーズに移行しました",
        "tech_stack": tech_stack,
        "architecture": architecture,
        "coder_response": code_request
    }

async def generate_tech_stack(requirements: str, constraints: list) -> Dict[str, Any]:
    """要件に基づいて技術スタックを決定"""
    # 簡単な例: 要件に基づいて技術を選択
    tech_stack = {
        "backend": "PHP 8.2",
        "database": "MySQL 8.0",
        "cache": "Redis",
        "web_server": "Nginx",
        "container": "Docker"
    }
    
    # 制約に基づいて調整
    for constraint in constraints:
        if "python" in constraint.lower():
            tech_stack["backend"] = "Python 3.11"
        elif "node" in constraint.lower():
            tech_stack["backend"] = "Node.js 22"
    
    return tech_stack

async def generate_architecture(requirements: str) -> Dict[str, Any]:
    """アーキテクチャ設計を生成"""
    architecture = {
        "pattern": "MVC",
        "layers": ["Controller", "Service", "Repository", "Model"],
        "components": {
            "api_endpoints": await extract_endpoints(requirements),
            "database_tables": await extract_tables(requirements),
            "services": await extract_services(requirements)
        }
    }
    
    return architecture

async def extract_endpoints(requirements: str) -> list:
    """要件からAPIエンドポイントを抽出"""
    # 簡単な例
    if "認証" in requirements or "ログイン" in requirements:
        return ["/api/auth/login", "/api/auth/logout", "/api/auth/register"]
    elif "ユーザー" in requirements:
        return ["/api/users", "/api/users/{id}"]
    else:
        return ["/api/health"]

async def extract_tables(requirements: str) -> list:
    """要件からデータベーステーブルを抽出"""
    tables = []
    if "ユーザー" in requirements or "認証" in requirements:
        tables.append("users")
    if "商品" in requirements or "プロダクト" in requirements:
        tables.append("products")
    return tables or ["sample_table"]

async def extract_services(requirements: str) -> list:
    """要件からサービスクラスを抽出"""
    services = []
    if "認証" in requirements:
        services.append("AuthService")
    if "ユーザー" in requirements:
        services.append("UserService")
    return services or ["SampleService"]

async def generate_file_list(requirements: str) -> list:
    """生成すべきファイルのリストを作成"""
    files = ["src/index.php", "src/config/database.php"]
    
    if "認証" in requirements:
        files.extend([
            "src/controllers/AuthController.php",
            "src/services/AuthService.php",
            "src/models/User.php"
        ])
    
    return files

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
    uvicorn.run(app, host="0.0.0.0", port=8081)
