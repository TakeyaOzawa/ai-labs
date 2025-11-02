"""
Notion API連携クライアント
"""
import os
from typing import Dict, List, Optional
from notion_client import Client
import logging

class NotionClient:
    def __init__(self):
        self.api_token = os.getenv('NOTION_API_TOKEN')
        self.database_id = os.getenv('NOTION_DATABASE_ID')
        self.workspace_url = os.getenv('NOTION_WORKSPACE_URL')
        self.logger = logging.getLogger(__name__)
        
        if not self.api_token:
            self.logger.warning("NOTION_API_TOKEN not set, Notion integration disabled")
            self.client = None
        else:
            self.client = Client(auth=self.api_token)

    def create_page(self, title: str, content: str, properties: Optional[Dict] = None) -> Optional[str]:
        """Notionページを作成"""
        if not self.client or not self.database_id:
            self.logger.warning("Notion client not configured")
            return None
            
        try:
            page_properties = {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            }
            
            if properties:
                page_properties.update(properties)
            
            response = self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=page_properties,
                children=[
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [
                                {
                                    "type": "text",
                                    "text": {
                                        "content": content
                                    }
                                }
                            ]
                        }
                    }
                ]
            )
            
            page_id = response["id"]
            self.logger.info(f"Created Notion page: {page_id}")
            return page_id
            
        except Exception as e:
            self.logger.error(f"Failed to create Notion page: {e}")
            return None

    def update_page(self, page_id: str, properties: Dict) -> bool:
        """Notionページを更新"""
        if not self.client:
            return False
            
        try:
            self.client.pages.update(
                page_id=page_id,
                properties=properties
            )
            self.logger.info(f"Updated Notion page: {page_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update Notion page: {e}")
            return False

    def create_development_cycle_page(self, cycle_id: str, tasks: List[Dict], status: str = "In Progress") -> Optional[str]:
        """開発サイクル用のNotionページを作成"""
        title = f"Development Cycle: {cycle_id}"
        
        # タスクリストを文字列に変換
        task_list = "\n".join([f"- {task.get('description', 'No description')}" for task in tasks])
        content = f"Cycle ID: {cycle_id}\n\nTasks:\n{task_list}"
        
        properties = {
            "Status": {
                "select": {
                    "name": status
                }
            },
            "Cycle ID": {
                "rich_text": [
                    {
                        "text": {
                            "content": cycle_id
                        }
                    }
                ]
            }
        }
        
        return self.create_page(title, content, properties)
