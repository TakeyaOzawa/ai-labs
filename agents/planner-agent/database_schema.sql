-- 開発履歴管理用データベーススキーマ

-- 開発サイクルテーブル
CREATE TABLE development_cycles (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50) UNIQUE NOT NULL,
    start_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    total_tasks INTEGER DEFAULT 0,
    completed_tasks INTEGER DEFAULT 0,
    quality_score DECIMAL(3,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- タスクテーブル
CREATE TABLE tasks (
    id SERIAL PRIMARY KEY,
    task_id VARCHAR(50) UNIQUE NOT NULL,
    cycle_id VARCHAR(50) NOT NULL,
    task_type VARCHAR(30) NOT NULL,
    priority VARCHAR(10) NOT NULL,
    description TEXT NOT NULL,
    estimated_effort INTEGER NOT NULL,
    actual_effort INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    assigned_agent VARCHAR(30),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cycle_id) REFERENCES development_cycles(cycle_id)
);

-- 品質メトリクステーブル
CREATE TABLE quality_metrics (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50) NOT NULL,
    test_coverage DECIMAL(5,2),
    technical_debt_score DECIMAL(3,2),
    security_score DECIMAL(3,2),
    performance_score DECIMAL(3,2),
    code_complexity DECIMAL(5,2),
    bug_count INTEGER DEFAULT 0,
    vulnerability_count INTEGER DEFAULT 0,
    measured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (cycle_id) REFERENCES development_cycles(cycle_id)
);

-- 課題テーブル
CREATE TABLE issues (
    id SERIAL PRIMARY KEY,
    issue_id VARCHAR(50) UNIQUE NOT NULL,
    cycle_id VARCHAR(50) NOT NULL,
    issue_type VARCHAR(30) NOT NULL,
    severity VARCHAR(10) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    assigned_task_id VARCHAR(50),
    discovered_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    FOREIGN KEY (cycle_id) REFERENCES development_cycles(cycle_id),
    FOREIGN KEY (assigned_task_id) REFERENCES tasks(task_id)
);

-- 推奨事項テーブル
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50) NOT NULL,
    recommendation_type VARCHAR(30) NOT NULL,
    priority VARCHAR(10) NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    implemented_in_task_id VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    implemented_at TIMESTAMP,
    FOREIGN KEY (cycle_id) REFERENCES development_cycles(cycle_id),
    FOREIGN KEY (implemented_in_task_id) REFERENCES tasks(task_id)
);

-- エージェント通信ログテーブル
CREATE TABLE agent_communications (
    id SERIAL PRIMARY KEY,
    cycle_id VARCHAR(50),
    sender_agent VARCHAR(30) NOT NULL,
    receiver_agent VARCHAR(30) NOT NULL,
    message_type VARCHAR(50) NOT NULL,
    payload JSONB,
    response_payload JSONB,
    sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    received_at TIMESTAMP,
    response_time_ms INTEGER,
    status VARCHAR(20) NOT NULL DEFAULT 'sent',
    FOREIGN KEY (cycle_id) REFERENCES development_cycles(cycle_id)
);

-- インデックス作成
CREATE INDEX idx_development_cycles_status ON development_cycles(status);
CREATE INDEX idx_development_cycles_start_time ON development_cycles(start_time);
CREATE INDEX idx_tasks_cycle_id ON tasks(cycle_id);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_task_type ON tasks(task_type);
CREATE INDEX idx_quality_metrics_cycle_id ON quality_metrics(cycle_id);
CREATE INDEX idx_quality_metrics_measured_at ON quality_metrics(measured_at);
CREATE INDEX idx_issues_cycle_id ON issues(cycle_id);
CREATE INDEX idx_issues_status ON issues(status);
CREATE INDEX idx_issues_severity ON issues(severity);
CREATE INDEX idx_recommendations_cycle_id ON recommendations(cycle_id);
CREATE INDEX idx_recommendations_status ON recommendations(status);
CREATE INDEX idx_agent_communications_cycle_id ON agent_communications(cycle_id);
CREATE INDEX idx_agent_communications_sent_at ON agent_communications(sent_at);

-- 更新時刻自動更新のトリガー関数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- トリガー作成
CREATE TRIGGER update_development_cycles_updated_at BEFORE UPDATE ON development_cycles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_tasks_updated_at BEFORE UPDATE ON tasks FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
