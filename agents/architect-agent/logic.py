#!/usr/bin/env python3
"""
ArchitectAgent - システム設計とアーキテクチャ決定
"""

import os
import sys
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uvicorn

sys.path.append('/app/common')
from role_config import RoleManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="ArchitectAgent", version="1.0.0")
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
    return {"status": "healthy", "agent": "architect", "role": role_manager.role.name}

@app.post("/mcp")
async def handle_mcp_request(request: MCPRequest) -> MCPResponse:
    try:
        logger.info(f"Received command: {request.command} from {request.sender}")
        
        if request.command == "HEALTH_CHECK":
            return MCPResponse(
                status="success",
                message="ArchitectAgent is healthy",
                data={"capabilities": role_manager.role.capabilities}
            )
        
        return MCPResponse(
            status="error",
            message=f"Unknown command: {request.command}"
        )
            
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {
        "agent": "ArchitectAgent",
        "role": role_manager.role.name,
        "description": role_manager.role.description,
        "capabilities": role_manager.role.capabilities
    }

if __name__ == "__main__":
    role_manager.setup_environment()
    port = int(os.getenv("AGENT_PORT", 8081))
    uvicorn.run(app, host="0.0.0.0", port=port)
