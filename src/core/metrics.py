"""
Prometheus метрики для MassRecruitHub.

Соответствует требованиям 152-ФЗ: метрики не содержат ПДн,
только агрегированные count/summary/histogram.
"""

from prometheus_client import Counter, Gauge, Histogram

# === Pipeline metrics ===
candidates_total = Counter(
    "mrh_candidates_total",
    "Total candidates processed",
    ["status", "source"],
)

pipeline_duration_seconds = Histogram(
    "mrh_pipeline_duration_seconds",
    "End-to-end pipeline duration per candidate",
    ["agent_stage"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
)

queue_depth = Gauge(
    "mrh_queue_depth",
    "Current candidate queue depth",
    ["queue_name"],
)

human_review_required = Counter(
    "mrh_human_review_required_total",
    "Candidates requiring human review",
    ["stage"],
)

# === Agent-specific metrics ===
screener_questions_asked = Counter(
    "mrh_screener_questions_total",
    "Questions asked by screener agent",
)

interviewer_sessions = Counter(
    "mrh_interviewer_sessions_total",
    "Interview sessions conducted",
    ["outcome"],
)

interviewer_audio_duration_seconds = Histogram(
    "mrh_interviewer_audio_duration_seconds",
    "Duration of interview audio recordings",
    buckets=(30, 60, 120, 300, 600, 900, 1800),
)

# === ML metrics ===
propensity_score = Gauge(
    "mrh_propensity_score",
    "Propensity score prediction",
    ["model_version"],
)

propensity_prediction_duration = Histogram(
    "mrh_propensity_prediction_duration_seconds",
    "Duration of propensity prediction",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
)

# === Fairness ===
fairness_disparate_impact = Gauge(
    "mrh_fairness_disparate_impact",
    "Disparate impact ratio per demographic group",
    ["group"],
)

fairness_demographic_parity = Gauge(
    "mrh_fairness_demographic_parity",
    "Demographic parity difference",
)

fairness_false_rejection_rate = Gauge(
    "mrh_fairness_false_rejection_rate",
    "False rejection rate per demographic group",
    ["group"],
)

# === Performance ===
semantic_cache_hits = Counter(
    "mrh_semantic_cache_hits_total",
    "Semantic cache hit count",
)

semantic_cache_misses = Counter(
    "mrh_semantic_cache_misses_total",
    "Semantic cache miss count",
)

semantic_cache_lookup_duration = Histogram(
    "mrh_semantic_cache_lookup_duration_seconds",
    "Semantic cache lookup duration",
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
)

# === Celery metrics ===
celery_queue_length = Gauge(
    "celery_queue_length",
    "Current length of Celery queue",
    ["queue_name"],
)

celery_task_duration_seconds = Histogram(
    "celery_task_duration_seconds",
    "Duration of Celery task execution",
    ["task_name", "queue"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

celery_tasks_total = Counter(
    "celery_tasks_total",
    "Total Celery tasks processed",
    ["task_name", "status"],
)

# === Deletion (right to be forgotten) ===
deletion_requests = Counter(
    "mrh_deletion_requests_total",
    "Total data deletion requests",
    ["status"],
)
