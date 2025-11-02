from fastapi import FastAPI, Request
import json
import logging
import sys
import os
from typing import Dict, Any

# 共通モジュールのパスを追加
sys.path.append('/app/common')
from agent_communicator import AgentCommunicator
from external_env_client import ExternalEnvironmentClient

app = FastAPI()
AGENT_NAME = "TesterAgent"

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# エージェント通信クライアント
communicator = AgentCommunicator("Tester")
external_client = ExternalEnvironmentClient()

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """MCPエンドポイント: テストタスクを受け取り、実行する"""
    data = await request.json()
    sender = data.get("sender", "Unknown")
    command = data.get("command", "UNKNOWN")
    payload = data.get("payload", {})
    
    logger.info(f"[{AGENT_NAME}] Received {command} from {sender}")
    
    if command == "TEST_REQUEST":
        return await handle_test_request(payload)
    else:
        return {"status": "error", "message": f"Unknown command: {command}"}

async def handle_test_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """テストリクエストの処理"""
    task_id = payload.get("task_id", "")
    test_type = payload.get("test_type", "unit")
    target_files = payload.get("target_files", [])
    external_services = payload.get("external_services", [])
    
    logger.info(f"[{AGENT_NAME}] Processing test request: {task_id}, type: {test_type}")
    
    if test_type == "integration":
        test_results = await run_integration_tests(target_files, external_services)
    elif test_type == "e2e":
        test_results = await run_e2e_tests(target_files)
    else:
        test_results = await run_unit_tests(target_files)
    
    # CoderAgentに結果を報告
    result_report = await communicator.send_command("coder", "TEST_RESULT", {
        "task_id": task_id,
        "status": "pass" if test_results["overall_success"] else "fail",
        "results": test_results,
        "generated_files": target_files
    })
    
    return {
        "status": "test_completed",
        "message": f"テスト実行が完了しました: {'成功' if test_results['overall_success'] else '失敗'}",
        "test_results": test_results,
        "coder_response": result_report
    }

async def run_integration_tests(target_files: list, external_services: list) -> Dict[str, Any]:
    """統合テスト実行"""
    logger.info(f"[{AGENT_NAME}] Running integration tests for {len(target_files)} files")
    
    results = {
        "test_type": "integration",
        "target_files": target_files,
        "external_services": external_services,
        "tests": {},
        "overall_success": True
    }
    
    # 外部環境の健全性チェック
    if "mysql" in external_services:
        mysql_test = await test_mysql_connection()
        results["tests"]["mysql_connection"] = mysql_test
        if not mysql_test["success"]:
            results["overall_success"] = False
    
    if "redis" in external_services:
        redis_test = await test_redis_connection()
        results["tests"]["redis_connection"] = redis_test
        if not redis_test["success"]:
            results["overall_success"] = False
    
    # ファイル固有のテスト
    for file_path in target_files:
        file_test = await test_generated_file(file_path)
        results["tests"][file_path] = file_test
        if not file_test["success"]:
            results["overall_success"] = False
    
    # 統合テストシナリオ
    integration_scenario = await run_integration_scenario()
    results["tests"]["integration_scenario"] = integration_scenario
    if not integration_scenario["success"]:
        results["overall_success"] = False
    
    return results

async def test_mysql_connection() -> Dict[str, Any]:
    """MySQL接続テスト"""
    try:
        result = await external_client.execute_mysql_query("SELECT 1 as test")
        return {
            "success": result["success"],
            "message": "MySQL connection successful" if result["success"] else "MySQL connection failed",
            "data": result.get("data")
        }
    except Exception as e:
        return {"success": False, "message": f"MySQL test failed: {str(e)}"}

async def test_redis_connection() -> Dict[str, Any]:
    """Redis接続テスト"""
    try:
        result = await external_client.execute_redis_command("ping")
        return {
            "success": result["success"] and result.get("data") == "PONG",
            "message": "Redis connection successful" if result["success"] else "Redis connection failed",
            "data": result.get("data")
        }
    except Exception as e:
        return {"success": False, "message": f"Redis test failed: {str(e)}"}

async def test_generated_file(file_path: str) -> Dict[str, Any]:
    """生成されたファイルのテスト"""
    try:
        project_root = "/app/project_root"
        full_path = os.path.join(project_root, file_path)
        
        if not os.path.exists(full_path):
            return {"success": False, "message": f"File not found: {file_path}"}
        
        # ファイルの基本チェック
        with open(full_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 基本的な構文チェック
        if file_path.endswith('.php'):
            syntax_check = await check_php_syntax(content)
        elif file_path.endswith('.py'):
            syntax_check = await check_python_syntax(content)
        else:
            syntax_check = {"valid": True, "message": "No syntax check available"}
        
        return {
            "success": syntax_check["valid"],
            "message": f"File test for {file_path}: {syntax_check['message']}",
            "file_size": len(content),
            "syntax_check": syntax_check
        }
    except Exception as e:
        return {"success": False, "message": f"File test failed: {str(e)}"}

async def check_php_syntax(content: str) -> Dict[str, Any]:
    """PHP構文チェック"""
    # 基本的なPHP構文チェック
    if "<?php" not in content:
        return {"valid": False, "message": "Missing PHP opening tag"}
    
    if content.count("{") != content.count("}"):
        return {"valid": False, "message": "Mismatched braces"}
    
    return {"valid": True, "message": "PHP syntax appears valid"}

async def check_python_syntax(content: str) -> Dict[str, Any]:
    """Python構文チェック"""
    try:
        compile(content, '<string>', 'exec')
        return {"valid": True, "message": "Python syntax is valid"}
    except SyntaxError as e:
        return {"valid": False, "message": f"Python syntax error: {str(e)}"}

async def run_integration_scenario() -> Dict[str, Any]:
    """統合テストシナリオ実行"""
    try:
        # データベースにテストデータを挿入
        insert_result = await external_client.execute_mysql_query(
            "CREATE TEMPORARY TABLE test_integration (id INT, name VARCHAR(50))"
        )
        
        if not insert_result["success"]:
            return {"success": False, "message": "Failed to create test table"}
        
        # テストデータ挿入
        data_result = await external_client.execute_mysql_query(
            "INSERT INTO test_integration VALUES (1, 'test_user')"
        )
        
        if not data_result["success"]:
            return {"success": False, "message": "Failed to insert test data"}
        
        # データ取得テスト
        select_result = await external_client.execute_mysql_query(
            "SELECT * FROM test_integration WHERE id = 1"
        )
        
        if not select_result["success"] or not select_result["data"]:
            return {"success": False, "message": "Failed to retrieve test data"}
        
        # Redisキャッシュテスト
        cache_set = await external_client.execute_redis_command("set", "test_key", "test_value")
        cache_get = await external_client.execute_redis_command("get", "test_key")
        
        if not (cache_set["success"] and cache_get["success"] and cache_get["data"] == "test_value"):
            return {"success": False, "message": "Redis cache test failed"}
        
        # クリーンアップ
        await external_client.execute_redis_command("del", "test_key")
        
        return {
            "success": True,
            "message": "Integration scenario completed successfully",
            "steps_completed": ["database_create", "data_insert", "data_select", "cache_test"]
        }
        
    except Exception as e:
        return {"success": False, "message": f"Integration scenario failed: {str(e)}"}

async def run_unit_tests(target_files: list) -> Dict[str, Any]:
    """単体テスト実行"""
    return {
        "test_type": "unit",
        "target_files": target_files,
        "overall_success": True,
        "message": "Unit tests completed (mock implementation)"
    }

async def run_e2e_tests(target_files: list) -> Dict[str, Any]:
    """E2Eテスト実行"""
    return {
        "test_type": "e2e",
        "target_files": target_files,
        "overall_success": True,
        "message": "E2E tests completed (mock implementation)"
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
    uvicorn.run(app, host="0.0.0.0", port=8083)
