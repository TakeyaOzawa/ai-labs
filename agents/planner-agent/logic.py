#!/usr/bin/env python3
"""
PlannerAgent - タスク計画・指示・再帰的開発サイクル管理
"""

import os
import sys
import asyncio
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn

# 共通モジュールをインポート
sys.path.append('/app/common')
from role_config import RoleManager

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PlannerAgent", version="1.0.0")

# 役割管理システム初期化
role_manager = RoleManager()

class MCPRequest(BaseModel):
    command: str
    sender: str
    payload: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None

@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy", "agent": "planner", "role": role_manager.role.name}

@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    """MCP (Model Context Protocol) リクエストハンドラー"""
    try:
        logger.info(f"Received command: {request.command} from {request.sender}")
        
        if request.command == "HEALTH_CHECK":
            return MCPResponse(
                status="success",
                message="PlannerAgent is healthy",
                data={"capabilities": role_manager.role.capabilities}
            )
        
        elif request.command == "INITIAL_TASK":
            # 初期タスク処理のプレースホルダー
            return MCPResponse(
                status="success",
                message="Initial task received and processing started",
                data={"task_id": "task_001"}
            )
        
        else:
            return MCPResponse(
                status="error",
                message=f"Unknown command: {request.command}"
            )
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    """ルートエンドポイント"""
    return {
        "agent": "PlannerAgent",
        "role": role_manager.role.name,
        "description": role_manager.role.description,
        "capabilities": role_manager.role.capabilities
    }

if __name__ == "__main__":
    # 役割設定を適用
    role_manager.setup_environment()
    
    # サーバー起動
    port = int(os.getenv("AGENT_PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
