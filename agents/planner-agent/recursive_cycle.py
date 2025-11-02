"""
PlannerAgent 再帰的開発サイクル実装
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import yaml

class Priority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

class TaskType(Enum):
    SECURITY_FIX = "security_fix"
    BUG_FIX = "bug_fix"
    QUALITY_IMPROVEMENT = "quality_improvement"
    FEATURE_ENHANCEMENT = "feature_enhancement"
    TECHNICAL_IMPROVEMENT = "technical_improvement"

@dataclass
class Issue:
    id: str
    type: str
    severity: Priority
    description: str
    estimated_effort: int

@dataclass
class QualityMetrics:
    test_coverage: float
    technical_debt_score: float
    security_score: float
    performance_score: float

@dataclass
class CompletionReport:
    cycle_id: str
    completed_tasks: List[str]
    test_results: Dict
    quality_metrics: QualityMetrics
    discovered_issues: List[Issue]
    recommendations: List[str]
    timestamp: datetime

@dataclass
class TaskCandidate:
    id: str
    type: TaskType
    priority: Priority
    description: str
    estimated_effort: int
    dependencies: List[str]

@dataclass
class DevelopmentPlan:
    cycle_id: str
    tasks: List[TaskCandidate]
    estimated_duration: int
    resource_requirements: Dict
    success_criteria: List[str]

class RecursiveCycleManager:
    def __init__(self, config_path: str = "planner_config.yaml"):
        self.config = self._load_config(config_path)
        self.logger = logging.getLogger(__name__)
        self.current_cycle = 0
        self.is_running = False
        
    def _load_config(self, config_path: str) -> Dict:
        """設定ファイルを読み込み"""
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """デフォルト設定"""
        return {
            'recursive_cycle': {
                'enabled': True,
                'max_cycles': 100,
                'cycle_interval_minutes': 30
            },
            'quality_thresholds': {
                'min_test_coverage': 90,
                'max_technical_debt_score': 6.0,
                'min_security_score': 7.0
            },
            'priority_weights': {
                'security': 1.0,
                'bugs': 0.8,
                'quality': 0.6,
                'features': 0.4
            }
        }

    async def process_completion_report(self, report: CompletionReport) -> Optional[DevelopmentPlan]:
        """完了報告を処理し、次期開発計画を策定"""
        if not self.config['recursive_cycle']['enabled']:
            return None
            
        self.logger.info(f"Processing completion report for cycle {report.cycle_id}")
        
        # 1. 完了報告を分析
        analysis_result = self._analyze_completion_report(report)
        
        # 2. 次期開発候補を抽出
        candidates = self._extract_task_candidates(analysis_result, report)
        
        # 3. 優先度付け
        prioritized_tasks = self._prioritize_tasks(candidates)
        
        # 4. 開発計画策定
        if prioritized_tasks:
            plan = self._generate_development_plan(prioritized_tasks)
            
            # 5. 次期開発指示発行
            await self._issue_development_instruction(plan)
            return plan
            
        return None

    def _analyze_completion_report(self, report: CompletionReport) -> Dict:
        """完了報告を分析"""
        analysis = {
            'quality_status': self._evaluate_quality(report.quality_metrics),
            'security_status': self._evaluate_security(report.quality_metrics.security_score),
            'issues_severity': self._evaluate_issues(report.discovered_issues),
            'recommendations_priority': self._evaluate_recommendations(report.recommendations)
        }
        
        self.logger.info(f"Analysis result: {analysis}")
        return analysis

    def _evaluate_quality(self, metrics: QualityMetrics) -> str:
        """品質状況を評価"""
        thresholds = self.config['quality_thresholds']
        
        if (metrics.test_coverage < thresholds['min_test_coverage'] or
            metrics.technical_debt_score > thresholds['max_technical_debt_score']):
            return "needs_improvement"
        return "acceptable"

    def _evaluate_security(self, security_score: float) -> str:
        """セキュリティ状況を評価"""
        min_score = self.config['quality_thresholds']['min_security_score']
        return "critical" if security_score < min_score else "acceptable"

    def _evaluate_issues(self, issues: List[Issue]) -> str:
        """発見された課題の重要度を評価"""
        critical_count = sum(1 for issue in issues if issue.severity == Priority.CRITICAL)
        return "critical" if critical_count > 0 else "manageable"

    def _evaluate_recommendations(self, recommendations: List[str]) -> str:
        """推奨事項の優先度を評価"""
        security_keywords = ['security', 'vulnerability', 'exploit']
        performance_keywords = ['performance', 'slow', 'optimization']
        
        for rec in recommendations:
            if any(keyword in rec.lower() for keyword in security_keywords):
                return "high"
            if any(keyword in rec.lower() for keyword in performance_keywords):
                return "medium"
        return "low"

    def _extract_task_candidates(self, analysis: Dict, report: CompletionReport) -> List[TaskCandidate]:
        """次期開発候補を抽出"""
        candidates = []
        
        # セキュリティ対応
        if analysis['security_status'] == 'critical':
            candidates.append(TaskCandidate(
                id=f"security_fix_{self.current_cycle}",
                type=TaskType.SECURITY_FIX,
                priority=Priority.CRITICAL,
                description="Critical security vulnerabilities fix",
                estimated_effort=8,
                dependencies=[]
            ))
        
        # 品質改善
        if analysis['quality_status'] == 'needs_improvement':
            candidates.append(TaskCandidate(
                id=f"quality_improvement_{self.current_cycle}",
                type=TaskType.QUALITY_IMPROVEMENT,
                priority=Priority.HIGH,
                description="Improve test coverage and reduce technical debt",
                estimated_effort=16,
                dependencies=[]
            ))
        
        # 発見された課題への対応
        for issue in report.discovered_issues:
            if issue.severity in [Priority.CRITICAL, Priority.HIGH]:
                candidates.append(TaskCandidate(
                    id=f"issue_fix_{issue.id}",
                    type=TaskType.BUG_FIX,
                    priority=issue.severity,
                    description=f"Fix issue: {issue.description}",
                    estimated_effort=issue.estimated_effort,
                    dependencies=[]
                ))
        
        return candidates

    def _prioritize_tasks(self, candidates: List[TaskCandidate]) -> List[TaskCandidate]:
        """タスクを優先度順にソート"""
        weights = self.config['priority_weights']
        
        def priority_score(task: TaskCandidate) -> float:
            base_score = 4 - task.priority.value  # CRITICAL=3, HIGH=2, MEDIUM=1, LOW=0
            
            type_weight = {
                TaskType.SECURITY_FIX: weights['security'],
                TaskType.BUG_FIX: weights['bugs'],
                TaskType.QUALITY_IMPROVEMENT: weights['quality'],
                TaskType.FEATURE_ENHANCEMENT: weights['features'],
                TaskType.TECHNICAL_IMPROVEMENT: weights['features']
            }.get(task.type, 0.1)
            
            return base_score * type_weight
        
        return sorted(candidates, key=priority_score, reverse=True)

    def _generate_development_plan(self, tasks: List[TaskCandidate]) -> DevelopmentPlan:
        """開発計画を策定"""
        # リソース制限を考慮してタスクを選択
        selected_tasks = tasks[:3]  # 最大3タスク
        
        total_effort = sum(task.estimated_effort for task in selected_tasks)
        
        plan = DevelopmentPlan(
            cycle_id=f"cycle_{self.current_cycle + 1}",
            tasks=selected_tasks,
            estimated_duration=total_effort,
            resource_requirements={
                'cpu_cores': min(4, len(selected_tasks)),
                'memory_mb': 1024 * len(selected_tasks),
                'storage_gb': 10
            },
            success_criteria=[
                "All tasks completed successfully",
                "Test coverage maintained above 90%",
                "No critical security issues",
                "Performance regression < 5%"
            ]
        )
        
        self.logger.info(f"Generated development plan: {plan.cycle_id}")
        return plan

    async def _issue_development_instruction(self, plan: DevelopmentPlan):
        """ArchitectAgentに開発指示を発行"""
        instruction = {
            "command": "START_DEVELOPMENT_CYCLE",
            "sender": "PlannerAgent",
            "payload": {
                "cycle_id": plan.cycle_id,
                "tasks": [
                    {
                        "id": task.id,
                        "type": task.type.value,
                        "priority": task.priority.name,
                        "description": task.description,
                        "estimated_effort": task.estimated_effort
                    }
                    for task in plan.tasks
                ],
                "success_criteria": plan.success_criteria,
                "resource_limits": plan.resource_requirements
            }
        }
        
        # ArchitectAgentに送信（実装は既存のMCP通信を使用）
        self.logger.info(f"Issuing development instruction for {plan.cycle_id}")
        # await self.send_to_architect(instruction)

    async def start_recursive_cycle(self):
        """再帰的開発サイクルを開始"""
        if not self.config['recursive_cycle']['enabled']:
            self.logger.info("Recursive cycle is disabled")
            return
            
        self.is_running = True
        max_cycles = self.config['recursive_cycle']['max_cycles']
        
        self.logger.info(f"Starting recursive development cycle (max: {max_cycles})")
        
        while self.is_running and self.current_cycle < max_cycles:
            try:
                # サイクル間隔待機
                interval = self.config['recursive_cycle']['cycle_interval_minutes']
                await asyncio.sleep(interval * 60)
                
                # 次のサイクルを待機（完了報告受信待ち）
                self.logger.info(f"Waiting for completion report for cycle {self.current_cycle}")
                
            except Exception as e:
                self.logger.error(f"Error in recursive cycle: {e}")
                await asyncio.sleep(60)  # エラー時は1分待機

    def stop_recursive_cycle(self):
        """再帰的開発サイクルを停止"""
        self.is_running = False
        self.logger.info("Recursive development cycle stopped")
