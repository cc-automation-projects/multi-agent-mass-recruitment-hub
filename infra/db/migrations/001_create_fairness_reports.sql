-- Таблица для хранения результатов fairness-аудита
CREATE TABLE IF NOT EXISTS fairness_reports (
    id SERIAL PRIMARY KEY,
    report_date TIMESTAMP NOT NULL DEFAULT NOW(),
    demographic_parity FLOAT,
    disparate_impact FLOAT,
    false_rejection_rate FLOAT,
    rejection_rates JSONB,
    requires_review BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);
