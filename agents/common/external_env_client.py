import requests
import mysql.connector
import redis
import subprocess
import tempfile
import os
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ExternalEnvironmentClient:
    def __init__(self):
        self.endpoints = {
            "php": "php-app.external-env.svc.cluster.local:9000",
            "mysql": "mysql.external-env.svc.cluster.local:3306", 
            "redis": "redis.external-env.svc.cluster.local:6379",
            "nginx": "nginx.external-env.svc.cluster.local:80"
        }
        self.mysql_config = {
            "host": "mysql.external-env.svc.cluster.local",
            "port": 3306,
            "user": "testuser",
            "password": "testpass",
            "database": "testdb"
        }
    
    async def execute_php_command(self, command: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """PHP アプリケーションでコマンド実行"""
        try:
            url = f"http://{self.endpoints['nginx']}/api/execute"
            payload = {"command": command, "args": args or {}}
            response = requests.post(url, json=payload, timeout=30)
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "data": response.json() if response.status_code == 200 else None,
                "error": response.text if response.status_code != 200 else None
            }
        except Exception as e:
            logger.error(f"PHP command execution failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def execute_mysql_query(self, query: str, params: tuple = None) -> Dict[str, Any]:
        """MySQL データベースクエリ実行"""
        try:
            conn = mysql.connector.connect(**self.mysql_config)
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query, params or ())
            
            if query.strip().upper().startswith('SELECT'):
                result = cursor.fetchall()
            else:
                conn.commit()
                result = {"affected_rows": cursor.rowcount}
            
            cursor.close()
            conn.close()
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"MySQL query execution failed: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def execute_redis_command(self, command: str, *args) -> Dict[str, Any]:
        """Redis コマンド実行"""
        try:
            host, port = self.endpoints['redis'].split(':')
            r = redis.Redis(host=host, port=int(port), decode_responses=True)
            result = getattr(r, command.lower())(*args)
            return {"success": True, "data": result}
        except Exception as e:
            logger.error(f"Redis command execution failed: {str(e)}")
            return {"success": False, "error": str(e)}
