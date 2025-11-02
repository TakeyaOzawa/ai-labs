"""
エージェント役割設定システム
"""
import os
import sys
import yaml
from typing import Dict, List, Optional
from dataclasses import dataclass

# 共通モジュールパスを追加
sys.path.append('/app/common')

@dataclass
class AgentRole:
    name: str
    description: str
    capabilities: List[str]
    aws_permissions: List[str]
    q_commands: List[str]
    environment_vars: Dict[str, str]

class RoleManager:
    def __init__(self):
        self.agent_type = os.getenv('AGENT_TYPE', 'unknown')
        self.role_config_path = f"/app/roles/{self.agent_type}.yaml"
        self.role = self._load_role_config()

    def _load_role_config(self) -> AgentRole:
        """役割設定を読み込み"""
        try:
            with open(self.role_config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            return AgentRole(
                name=config.get('name', self.agent_type),
                description=config.get('description', ''),
                capabilities=config.get('capabilities', []),
                aws_permissions=config.get('aws_permissions', []),
                q_commands=config.get('q_commands', []),
                environment_vars=config.get('environment_vars', {})
            )
        except FileNotFoundError:
            return self._default_role()

    def _default_role(self) -> AgentRole:
        """デフォルト役割設定"""
        return AgentRole(
            name=self.agent_type,
            description=f"Default {self.agent_type} agent",
            capabilities=['basic_operations'],
            aws_permissions=[],
            q_commands=['q --help'],
            environment_vars={}
        )

    def setup_environment(self):
        """環境変数を設定"""
        for key, value in self.role.environment_vars.items():
            os.environ[key] = value

    def can_execute_command(self, command: str) -> bool:
        """コマンド実行権限をチェック"""
        return any(cmd in command for cmd in self.role.q_commands)

    def get_aws_profile_config(self) -> Dict:
        """AWS設定を取得"""
        return {
            'region': os.getenv('AWS_DEFAULT_REGION', 'us-east-1'),
            'permissions': self.role.aws_permissions
        }
