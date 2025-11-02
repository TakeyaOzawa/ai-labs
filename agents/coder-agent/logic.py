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
AGENT_NAME = "CoderAgent"

# ロギング設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# エージェント通信クライアント
communicator = AgentCommunicator("Coder")
external_client = ExternalEnvironmentClient()

@app.post("/mcp")
async def handle_mcp_request(request: Request):
    """MCPエンドポイント: コード生成タスクを受け取り、実装を行う"""
    data = await request.json()
    sender = data.get("sender", "Unknown")
    command = data.get("command", "UNKNOWN")
    payload = data.get("payload", {})
    
    logger.info(f"[{AGENT_NAME}] Received {command} from {sender}")
    
    if command == "CODE_REQUEST":
        return await handle_code_request(payload)
    elif command == "TEST_RESULT":
        return await handle_test_result(payload)
    else:
        return {"status": "error", "message": f"Unknown command: {command}"}

async def handle_code_request(payload: Dict[str, Any]) -> Dict[str, Any]:
    """コード生成リクエストを処理"""
    task_id = payload.get("task_id", "")
    specifications = payload.get("specifications", {})
    files = payload.get("files", [])
    
    logger.info(f"[{AGENT_NAME}] Processing code request: {task_id}")
    
    # コードを生成
    generated_files = await generate_code(specifications, files)
    
    # 生成したコードをproject_rootに保存
    await save_code_to_project_root(generated_files)
    
    # TesterAgentにテストを依頼
    test_request = await communicator.send_command("tester", "TEST_REQUEST", {
        "task_id": task_id,
        "test_type": "integration",
        "target_files": list(generated_files.keys()),
        "external_services": ["mysql", "redis"],
        "priority": "high"
    })
    
    return {
        "status": "code_generated",
        "message": "コードを生成し、テストフェーズに移行しました",
        "generated_files": list(generated_files.keys()),
        "tester_response": test_request
    }

async def generate_code(specifications: Dict[str, Any], files: list) -> Dict[str, str]:
    """仕様に基づいてコードを生成"""
    tech_stack = specifications.get("tech_stack", {})
    architecture = specifications.get("architecture", {})
    requirements = specifications.get("requirements", "")
    
    generated_files = {}
    
    for file_path in files:
        if file_path.endswith(".php"):
            generated_files[file_path] = await generate_php_file(file_path, specifications)
        elif file_path.endswith(".py"):
            generated_files[file_path] = await generate_python_file(file_path, specifications)
        else:
            generated_files[file_path] = await generate_generic_file(file_path, specifications)
    
    return generated_files

async def generate_php_file(file_path: str, specifications: Dict[str, Any]) -> str:
    """PHPファイルを生成"""
    if "AuthController" in file_path:
        return """<?php
class AuthController {
    private $db;
    
    public function __construct($database) {
        $this->db = $database;
    }
    
    public function login($request) {
        $username = $request['username'];
        $password = $request['password'];
        
        // 認証ロジック
        $user = $this->db->query("SELECT * FROM users WHERE username = ?", [$username]);
        
        if ($user && password_verify($password, $user['password'])) {
            return ['status' => 'success', 'token' => 'jwt_token_here'];
        }
        
        return ['status' => 'error', 'message' => 'Invalid credentials'];
    }
    
    public function logout() {
        return ['status' => 'success', 'message' => 'Logged out'];
    }
}
?>"""
    elif "User" in file_path:
        return """<?php
class User {
    private $db;
    
    public function __construct($database) {
        $this->db = $database;
    }
    
    public function create($userData) {
        $hashedPassword = password_hash($userData['password'], PASSWORD_DEFAULT);
        
        return $this->db->query(
            "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
            [$userData['username'], $userData['email'], $hashedPassword]
        );
    }
    
    public function findById($id) {
        return $this->db->query("SELECT * FROM users WHERE id = ?", [$id]);
    }
}
?>"""
    else:
        return """<?php
// Generated PHP file
echo "Hello from generated PHP code!";
?>"""

async def generate_python_file(file_path: str, specifications: Dict[str, Any]) -> str:
    """Pythonファイルを生成"""
    return """# Generated Python file
def main():
    print("Hello from generated Python code!")

if __name__ == "__main__":
    main()
"""

async def generate_generic_file(file_path: str, specifications: Dict[str, Any]) -> str:
    """汎用ファイルを生成"""
    if file_path.endswith(".sql"):
        return """-- Generated SQL file
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
    else:
        return f"# Generated file: {file_path}\n# Content based on specifications"

async def save_code_to_project_root(generated_files: Dict[str, str]):
    """生成したコードをproject_rootに保存"""
    project_root = "/app/project_root"
    
    for file_path, content in generated_files.items():
        full_path = os.path.join(project_root, file_path)
        
        # ディレクトリを作成
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # ファイルを保存
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"[{AGENT_NAME}] Saved file: {full_path}")

async def handle_test_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    """テスト結果を処理"""
    task_id = payload.get("task_id", "")
    status = payload.get("status", "")
    results = payload.get("results", {})
    
    logger.info(f"[{AGENT_NAME}] Received test result for {task_id}: {status}")
    
    if status == "pass":
        # テスト成功 - PlannerAgentに完了報告
        completion_report = await communicator.send_command("planner", "TASK_COMPLETE", {
            "task_id": task_id,
            "result": "success",
            "artifacts": results.get("generated_files", []),
            "test_results": results
        })
        
        return {
            "status": "task_completed",
            "message": "テストが成功し、タスクが完了しました",
            "planner_response": completion_report
        }
    else:
        # テスト失敗 - コードを修正
        logger.warning(f"[{AGENT_NAME}] Tests failed, attempting to fix code")
        return {
            "status": "fixing_code",
            "message": "テストが失敗したため、コードを修正中です",
            "errors": results.get("errors", [])
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
    uvicorn.run(app, host="0.0.0.0", port=8082)
