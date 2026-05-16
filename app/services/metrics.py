from prometheus_client import Counter, Histogram

GIGACHAT_REQUESTS = Counter(
    "gigachat_requests_total",
    "Total GigaChat API requests",
    ["operation", "status"],
)

GIGACHAT_DURATION = Histogram(
    "gigachat_request_duration_seconds",
    "GigaChat API request duration in seconds",
    ["operation"],
    buckets=[1, 2, 5, 10, 20, 30, 60, 120],
)

GIGACHAT_TOKEN_REFRESHES = Counter(
    "gigachat_token_refreshes_total",
    "Number of GigaChat OAuth token refreshes",
)

# Воронка пользователей
SESSIONS_STARTED = Counter(
    "chatbot_sessions_started_total",
    "Number of chat sessions started",
)

CONTACTS_SUBMITTED = Counter(
    "chatbot_contacts_submitted_total",
    "Number of times contacts were submitted by users",
)

REPORTS_GENERATED = Counter(
    "chatbot_reports_generated_total",
    "Number of PDF reports successfully generated",
)

REPORTS_FAILED = Counter(
    "chatbot_reports_failed_total",
    "Number of PDF report generation failures",
)