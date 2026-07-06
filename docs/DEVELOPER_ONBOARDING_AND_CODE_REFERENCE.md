# Руководство по онбордингу разработчиков и справочник по коду Multi-Agent Mass Recruitment Hub

## 1. Введение в проект для разработчиков

Multi-Agent Mass Recruitment Hub — это мультиагентная система массового рекрутинга с голосовым и текстовым интерфейсами. Она автоматизирует полную воронку найма: от первичного скрининга кандидатов до онбординга и аналитики, используя пять специализированных AI-агентов, оркестрируемых через LangGraph. Система построена на современном стеке: Python 3.12, FastAPI, LangGraph, LiveKit, FreeSWITCH, Qdrant, PostgreSQL, Redis, Celery, и развёртывается в Kubernetes.

Этот документ создан, чтобы помочь новым разработчикам быстро погрузиться в проект, понять его архитектуру, структуру кода и процессы разработки. Здесь вы найдёте пошаговую инструкцию для запуска проекта, подробное описание структуры каталогов, справочник по ключевым файлам, правила оформления кода, git-процессы, гайд по контрибуции и сжатое архитектурное ревью с указанием текущих проблем и направлений развития. Документ построен так, чтобы вы могли начать работать с кодом в течение первого часа, а затем углубляться в отдельные аспекты по мере необходимости, обращаясь к смежным документам из нашего пакета спецификаций.

## 2. Быстрый старт (1 час)

### 2.1. Требования к рабочему окружению

Для работы над проектом вам понадобятся следующие инструменты:
- **Python 3.12+** — рекомендуется использовать `pyenv` для управления версиями.
- **Node.js v20+** — требуется для работы с LiveKit Agents (если вы будете модифицировать frontend или голосовой пайплайн).
- **Docker 24+ и Docker Compose 2.20+** — для запуска локального dev-стека с базами данных, телефонией и системами мониторинга.
- **Git 2.30+** — для управления версиями.
- **Make** (опционально) — для удобного запуска команд.

### 2.2. Пошаговая инструкция по запуску

Следуйте командам ниже, чтобы развернуть проект локально:

```bash
# 1. Клонируйте репозиторий
git clone https://github.com/company/mass-recruit-hub.git
cd mass-recruit-hub

# 2. Запустите все зависимые сервисы (PostgreSQL, Redis, Qdrant, LiveKit, FreeSWITCH, ELK, Prometheus, Grafana)
docker-compose -f docker-compose.yml up -d

# 3. Создайте файл с переменными окружения и настройте его под свои нужды
cp .env.example .env
# Для локальной разработки достаточно оставить значения по умолчанию.
# Для работы с LLM, Telegram, VK и другими сервисами добавьте реальные ключи.

# 4. Создайте виртуальное окружение и установите зависимости
python -m venv venv
source venv/bin/activate  # или `venv\Scripts\activate` на Windows
pip install -e ".[dev]"

# 5. Примените миграции базы данных
alembic upgrade head

# 6. Загрузите тестовые данные (опционально)
python scripts/init_dev_db.py

# 7. Проверьте, что всё работает, запустив unit-тесты
pytest tests/ -m unit -v

# 8. Запустите приложение в режиме разработки
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 9. Проверьте, что API отвечает
curl http://localhost:8000/health
```

### 2.3. Ключевые переменные окружения

В файле `.env` определены все настройки системы. Для разработки важно знать следующие переменные:

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| `DATABASE_URL` | Строка подключения к PostgreSQL | `postgresql+psycopg2://user:password@localhost:5432/Multi-Agent Mass Recruitment Hub` |
| `REDIS_URL` | Строка подключения к Redis | `redis://localhost:6379/0` |
| `QDRANT_URL` | HTTP-эндпоинт Qdrant | `http://localhost:6333` |
| `LLM_ENDPOINT` | Эндпоинт YandexGPT | `https://llm.api.yandex.cloud/v1` |
| `LLM_API_KEY` | API-ключ для YandexGPT | (обязателен для работы с LLM) |
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота | (обязателен для интеграции с Telegram) |
| `FREESWITCH_HOST` | Хост FreeSWITCH для ESL-подключения | `localhost` |
| `LIVEKIT_HOST` | Хост LiveKit Server | `localhost` |

Все переменные типизированы и валидируются через Pydantic в [src/core/config.py](../src/core/config.py). Если вы используете моки для внешних сервисов (например, `USE_MOCK_LLM=true`), API-ключи не требуются.

## 3. Структура проекта

### 3.1. Дерево проекта (по логическим группам)

#### Корень проекта

```
mass-recruit-hub/
├── pyproject.toml              # Зависимости Python, линтеры, метаданные
├── Dockerfile                  # Production-сборка (multi-stage)
├── Dockerfile.dev              # Dev-сборка
├── docker-compose.yml          # Локальный стек (БД, LiveKit, FreeSWITCH, ELK, мониторинг)
├── alembic.ini                 # Конфигурация Alembic (миграции БД)
├── pytest.ini                  # Настройки pytest
├── .env.example                # Шаблон переменных окружения
├── .gitignore                  # Исключения Git
├── README.md                   # Общее описание проекта
└── LICENSE                     # Лицензия
```

#### Основной код — `src/`

```
src/
├── main.py                     # Точка входа FastAPI (роутеры, CORS, /health, /metrics)
├── celery_app.py               # Celery-приложение (брокер Redis)
├── celery_metrics.py           # Prometheus-метрики для Celery
│
├── api/                        # FastAPI-роутеры и middleware
│   ├── auth.py                 #   JWT-аутентификация (register, login, refresh)
│   ├── campaigns.py            #   CRUD кампаний
│   ├── candidates.py           #   Кандидаты (с маскированием PII)
│   ├── admin.py                #   Админка: импорт, веса модели
│   ├── deletion.py             #   Право на забвение (152-ФЗ)
│   ├── deps.py                 #   Зависимости: БД, текущий пользователь, админ
│   ├── messenger_webhook.py    #   Вебхук мессенджеров (MAX, Telegram, VK)
│   ├── telegram_webhook.py     #   Вебхук Telegram-бота
│   └── rpa_webhook.py          #   Вебхук для RPA-интеграции
│
├── agents/                     # AI-агенты на LangGraph
│   ├── orchestrator.py         #   Оркестратор кампаний
│   ├── screener/               #   Агент-скринер (скрининг кандидатов)
│   │   ├── graph.py            #     Определение графа
│   │   └── nodes.py            #     Узлы: проверка согласия, анализ резюме, оценка
│   ├── interviewer/            #   Агент-интервьюер (голосовое интервью)
│   │   ├── graph.py            #     Определение графа
│   │   ├── nodes.py            #     Узлы: вопросы, диалог, просодия, видео
│   │   ├── prompts.py          #     Промпты для LLM
│   │   ├── prosody.py          #     Анализ просодии (librosa)
│   │   ├── video_analyzer.py   #     Видеоанализ (OpenCV + DeepFace)
│   │   └── face_utils.py       #     Утилиты для работы с лицом
│   ├── coordinator/            #   Агент-координатор (маршрутизация)
│   │   ├── graph.py            #     Определение графа
│   │   └── nodes.py            #     Узлы: роутинг, handoff, аналитика
│   ├── onboarding/             #   Агент-онбординг (приём нового сотрудника)
│   │   ├── graph.py            #     Определение графа
│   │   └── nodes.py            #     Узлы: документы, верификация, календарь
│   └── analyst/                #   Агент-аналитик (метрики и fairness)
│       ├── graph.py            #     Определение графа
│       ├── nodes.py            #     Узлы: метрики, fairness, отчёты
│       └── fairness_metrics.py #     Метрики fairness (demographic parity, DI)
│
├── core/                       # Базовые компоненты
│   ├── config.py               #   Pydantic-конфигурация (из .env)
│   ├── models.py               #   Pydantic-модели данных
│   ├── database.py             #   Асинхронный SQLAlchemy (PostgreSQL)
│   ├── state.py                #   Состояние графа LangGraph (AgentState)
│   ├── metrics.py              #   Prometheus-метрики
│   ├── audit_logger.py         #   Аудит-лог (structlog, 152-ФЗ ст. 18.1)
│   └── logging_config.py       #   Настройка логирования (JSON, Filebeat)
│
├── services/                   # Бизнес-сервисы
│   ├── campaign_service.py     #   CRUD кампаний
│   ├── deletion_service.py     #   Каскадное удаление (право на забвение)
│   ├── handoff_service.py      #   Омниканальный handoff (Redis)
│   ├── hr_integrations.py      #   Интеграции с HR-системами и мессенджерами
│   ├── import_resumes.py       #   Импорт резюме (hh.ru, Avito)
│   ├── propensity_dialer.py    #   Пропенсити-дайлер (CatBoost)
│   ├── semantic_cache.py       #   MVR-кэш для LLM (Qdrant)
│   ├── qdrant_storage.py       #   Работа с Qdrant (векторное хранение)
│   ├── calendar_service.py     #   Интеграция с календарями
│   ├── audio_converter.py      #   Конвертация аудиоформатов
│   ├── model_weights_service.py#   Управление весами модели
│   ├── agent_runner.py         #   Запуск агентов
│   ├── rpa_client.py           #   Клиент для RPA
│   └── biometry_consent.py     #   Согласие на биометрию
│
├── voice/                      # Голосовой пайплайн
│   ├── pipeline.py             #   Основной цикл: ASR → LLM → TTS
│   ├── livekit_client.py       #   Клиент LiveKit Server
│   ├── asr.py                  #   Распознавание речи (Whisper)
│   └── tts.py                  #   Синтез речи (Silero, заглушка)
│
├── telephony/                  # Телефония (FreeSWITCH)
│   ├── esl_client.py           #   Низкоуровневый ESL-клиент
│   └── freeswitch_client.py    #   Высокоуровневый клиент (make_call и др.)
│
├── llm/                        # LLM-клиенты
│   └── vllm_client.py          #   Клиент для vLLM (inference)
│
├── pii/                        # Анонимизация ПДн
│   ├── anonymizer.py           #   Обёртка Presidio (асинхронная)
│   └── recognizers.py          #   Распознаватели РФ-документов
│
├── bot/                        # Telegram-бот
│   └── telegram.py             #   Логика бота
│
├── tasks/                      # Celery-задачи
│   ├── campaign_tasks.py       #   Запуск кампаний
│   └── import_tasks.py         #   Импорт данных
│
├── integrations/               # Внешние интеграции
│   └── job_boards.py           #   hh.ru, Avito (REST API)
│
├── optimization/               # A/B-тестирование
│   ├── bandit.py               #   Multi-armed bandit
│   └── bandit_service.py       #   Сервис bandit
│
└── static/
    └── index.html              #   Админ-панель (управление весами)
```

#### Инфраструктура — `infra/`

```
infra/
├── helm/mass-recruit-hub/      # Helm-чарт для Kubernetes
│   ├── Chart.yaml              #   Метаданные чарта
│   ├── values.yaml             #   Значения (dev)
│   ├── values-prod.yaml        #   Значения (prod)
│   └── templates/              #   Шаблоны K8s
│       ├── deployment.yaml     #     Deployment
│       ├── service.yaml        #     Service
│       ├── ingress.yaml        #     Ingress
│       ├── configmap.yaml      #     ConfigMap
│       ├── secret.yaml         #     Secret
│       ├── externalsecret.yaml #     ExternalSecret (Vault / Lockbox)
│       ├── hpa.yaml            #     HPA (автоскалинг)
│       ├── serviceaccount.yaml #     ServiceAccount
│       ├── servicemonitor.yaml #     ServiceMonitor (Prometheus Operator)
│       └── grafana-dashboard-configmap.yaml
│
├── terraform/
│   └── main.tf                 # Terraform для Yandex Cloud
│
├── docker/                     # Docker-образы
│   ├── init-pgvector.sql       #   Инициализация pgvector
│   └── freeswitch/             #   FreeSWITCH
│       └── conf/autoload_configs/
│           └── event_socket.conf.xml
│
├── livekit/
│   └── livekit.yaml            # Конфиг LiveKit Server
│
├── prometheus/
│   ├── prometheus.yml          # Конфиг Prometheus
│   └── alerts.yaml             # Правила алертов
│
├── grafana/
│   ├── datasource.yaml         # Datasource (Prometheus)
│   └── dashboard-mass-recruit-hub.json  # Дашборд
│
├── elk/
│   └── logstash.conf           # Logstash pipeline
│
├── filebeat/
│   └── filebeat.yml            # Filebeat (сбор логов)
│
└── db/
    └── migrations/
        └── 001_create_fairness_reports.sql  # Миграции БД
```

#### Тесты — `tests/`

```
tests/
├── unit/
│   └── test_semantic_cache.py      # Unit-тест кэша
│
├── integration/
│   ├── test_screener_e2e.py        # E2E скринера
│   ├── test_interviewer_e2e.py     # E2E интервьюера
│   ├── test_coordinator_e2e.py     # E2E координатора
│   ├── test_onboarding_e2e.py      # E2E онбординга
│   └── test_analyst_e2e.py         # E2E аналитика
│
├── test_screener_graph.py          # Тест графа скринера
├── test_interviewer_graph.py       # Тест графа интервьюера
└── test_coordinator_graph.py       # Тест графа координатора
```

#### Документация — `docs/`

```
docs/                               # Спецификации и гайды (RU)
├── SYSTEM_SPECIFICATION_AND_PRODUCT_GUIDE.md         # Бизнес-контекст, FR/NFR, продукт
├── ARCHITECTURE_AND_DATA_MODEL.md                     # Архитектура, C4, модель данных
├── AI_AGENT_AND_ML_PIPELINE.md                        # AI-агенты, ML, fairness
├── API_AND_USER_INTERFACE_SPECIFICATION.md            # REST API, WebSocket, UI
├── VOICE_AND_TELEPHONY_PIPELINE.md                    # Голосовой пайплайн, телефония
├── DEPLOYMENT_OBSERVABILITY_AND_ADMIN_GUIDE.md        # Развёртывание, CI/CD, мониторинг
├── SECURITY_COMPLIANCE_AND_PRIVACY_GUIDE.md           # Безопасность, PII, 152-ФЗ, ФСТЭК
├── QUALITY_ASSURANCE_AND_TESTING_STRATEGY.md          # Тестирование, нагрузка
└── DEVELOPER_ONBOARDING_AND_CODE_REFERENCE.md         # Онбординг, структура, стиль кода
```

#### Вспомогательное

```
migrations/versions/             # Миграции БД (Alembic)
├── 001_initial_schema.py        #   Начальная схема
├── 002_add_model_weights.py     #   Таблица model_weights
├── 003_add_users.py             #   Таблица users
└── 004_add_biometry_consent_log.py  # Логи согласия на биометрию

evals/                           # LLM-оценки
├── evaluation-strategy.md       #   Стратегия оценки
├── test_hallucination.py        #   Тест галлюцинаций
└── __init__.py

scripts/                         # Скрипты
├── deploy-prod.sh               #   Деплой (bash)
├── run_vllm_server.py           #   Запуск vLLM
├── download_whisper_model.py    #   Загрузка модели Whisper
└── test_tts.py                  #   Тест TTS

audio/                           # Тестовые аудиофайлы
└── cand_intv_001.wav
```

### 3.2. Описание ключевых директорий

- **`src/api/`** — FastAPI-роутеры и middleware. Здесь реализованы все эндпоинты: аутентификация ([auth.py](../src/api/auth.py)), управление кампаниями ([campaigns.py](../src/api/campaigns.py)), кандидатами ([candidates.py](../src/api/candidates.py)), администрирование ([admin.py](../src/api/admin.py)), удаление данных ([deletion.py](../src/api/deletion.py)), вебхуки для мессенджеров ([messenger_webhook.py](../src/api/messenger_webhook.py), [telegram_webhook.py](../src/api/telegram_webhook.py)) и зависимости для авторизации ([deps.py](../src/api/deps.py)).
- **`src/agents/`** — реализация пяти AI-агентов на LangGraph. Каждый агент находится в своей поддиректории (`screener/`, `interviewer/`, `coordinator/`, `onboarding/`, `analyst/`) и содержит файлы `graph.py` (определение графа) и `nodes.py` (логика узлов). Также здесь находится оркестратор ([orchestrator.py](../src/agents/orchestrator.py)), который управляет запуском кампаний.
- **`src/core/`** — общие компоненты: конфигурация ([config.py](../src/core/config.py)), Pydantic-модели данных ([models.py](../src/core/models.py)), состояние графа ([state.py](../src/core/state.py)), подключение к БД ([database.py](../src/core/database.py)), Prometheus-метрики ([metrics.py](../src/core/metrics.py)), структурированное логирование ([audit_logger.py](../src/core/audit_logger.py), [logging_config.py](../src/core/logging_config.py)).
- **`src/pii/`** — анонимизация персональных данных с помощью Microsoft Presidio. Содержит асинхронную обёртку ([anonymizer.py](../src/pii/anonymizer.py)) и кастомные распознаватели для российских форматов документов ([recognizers.py](../src/pii/recognizers.py)).
- **`src/voice/`** — голосовой пайплайн: интеграция с LiveKit Agents ([livekit_client.py](../src/voice/livekit_client.py)) и основной цикл обработки аудио (ASR → LLM → TTS) в [pipeline.py](../src/voice/pipeline.py).
- **`src/telephony/`** — работа с FreeSWITCH через Event Socket Library (ESL). Низкоуровневый клиент ([esl_client.py](../src/telephony/esl_client.py)) и высокоуровневые функции для исходящих звонков ([freeswitch_client.py](../src/telephony/freeswitch_client.py)).
- **`src/services/`** — бизнес-сервисы: управление кампаниями ([campaign_service.py](../src/services/campaign_service.py)), удаление данных ([deletion_service.py](../src/services/deletion_service.py)), handoff ([handoff_service.py](../src/services/handoff_service.py)), интеграции с HR-системами ([hr_integrations.py](../src/services/hr_integrations.py)), импорт резюме ([import_resumes.py](../src/services/import_resumes.py)), пропенсити-дайлер ([propensity_dialer.py](../src/services/propensity_dialer.py)), работа с Qdrant ([qdrant_storage.py](../src/services/qdrant_storage.py)), семантический кэш ([semantic_cache.py](../src/services/semantic_cache.py)), календари ([calendar_service.py](../src/services/calendar_service.py)), конвертация аудио ([audio_converter.py](../src/services/audio_converter.py)).
- **`src/llm/`** — клиенты для LLM и роутер с поддержкой fallback (`llm_client.py`, `llm_router.py`).
- **`src/tasks/`** — Celery-задачи для фоновой обработки: запуск кампаний ([campaign_tasks.py](../src/tasks/campaign_tasks.py)), импорт данных ([import_tasks.py](../src/tasks/import_tasks.py)).
- **`src/integrations/`** — интеграции с внешними системами (hh.ru, Avito) через REST API ([job_boards.py](../src/integrations/job_boards.py)).
- **`src/optimization/`** — multi-armed bandit для A/B-тестирования скриптов приветствия ([bandit.py](../src/optimization/bandit.py), [bandit_service.py](../src/optimization/bandit_service.py)).
- **`src/bot/`** — Telegram-бот для общения с кандидатами ([telegram.py](../src/bot/telegram.py)).
- **`src/static/`** — статические файлы: минимальная админ-панель для управления весами модели ([index.html](../src/static/index.html)).
- **`infra/`** — инфраструктурные конфигурации: Helm-чарты для K8s, Terraform для Yandex Cloud, Docker-образы FreeSWITCH, конфиги Prometheus, Grafana, ELK и Filebeat.
- **`tests/`** — все тесты, организованные по типам: unit, integration, e2e. Подробное описание тестов см. в [QUALITY_ASSURANCE_AND_TESTING_STRATEGY.md](./QUALITY_ASSURANCE_AND_TESTING_STRATEGY.md).

## 4. Справочник по исходному коду (SOURCE_CODE_REFERENCE)

В этом разделе приведено описание ключевых файлов, их назначение, связанные требования и зависимости. Это поможет вам быстро ориентироваться в коде.

### 4.1. Точка входа и конфигурация

- [src/main.py](../src/main.py) — точка входа FastAPI-приложения. Создаёт экземпляр FastAPI, настраивает CORS, подключает все роутеры из `src/api/`, добавляет эндпоинты `/health` и `/metrics`. **Связанные требования:** NFR-4 (наблюдаемость). **ADR:** ADR-001 (FastAPI). **Зависимости:** все роутеры, [src/core/config.py](../src/core/config.py), `prometheus_client`.

- [src/core/config.py](../src/core/config.py) — централизованная конфигурация через Pydantic Settings. Загружает переменные окружения из `.env`, валидирует типы и предоставляет единый объект `settings`. **Связанные требования:** все FR (конфигурация влияет на всё). **ADR:** ADR-001 (Pydantic). **Зависимости:** `pydantic_settings`.

- [src/celery_app.py](../src/celery_app.py) — настройка Celery-приложения с брокером на Redis. Определяет все задачи и их конфигурацию (retry, таймауты, сериализация). **Связанные требования:** NFR-1 (производительность). **Зависимости:** `celery`, [src/core/config.py](../src/core/config.py).

### 4.2. API-слой (src/api/)

- [src/api/auth.py](../src/api/auth.py) — аутентификация и авторизация (JWT). Роутеры: `POST /auth/register` (регистрация), `POST /auth/login` (получение токена), `POST /auth/refresh` (обновление токена). **FR:** FR-7 (администрирование). **Зависимости:** [src/core/config.py](../src/core/config.py), [src/core/models.py](../src/core/models.py), `passlib`, `python-jose`.

- [src/api/campaigns.py](../src/api/campaigns.py) — управление рекрутинговыми кампаниями. Роутеры: `POST /campaigns` (создание), `GET /campaigns/{id}` (просмотр), `POST /campaigns/{id}/start` (запуск). **FR:** FR-7. **Зависимости:** [src/services/campaign_service.py](../src/services/campaign_service.py), [src/core/models.py](../src/core/models.py).

- [src/api/candidates.py](../src/api/candidates.py) — управление кандидатами. Роутеры: `POST /candidates` (создание, требует `consent_152fz=true`), `GET /candidates/{id}` (просмотр с маскированием PII). **FR:** FR-1, FR-7. **Зависимости:** [src/core/models.py](../src/core/models.py), [src/pii/anonymizer.py](../src/pii/anonymizer.py).

- [src/api/deletion.py](../src/api/deletion.py) — реализация права на забвение. Роутер: `POST /candidates/{id}/delete` (асинхронное каскадное удаление). **NFR:** NFR-3 (безопасность), 152-ФЗ ст. 15. **Зависимости:** [src/services/deletion_service.py](../src/services/deletion_service.py).

- [src/api/admin.py](../src/api/admin.py) — административные эндпоинты: импорт резюме с hh.ru (`POST /admin/import/hh`), управление весами модели (`GET/POST /admin/model/weights`). **FR:** FR-7. **Зависимости:** [src/services/model_weights_service.py](../src/services/model_weights_service.py), [src/tasks/import_tasks.py](../src/tasks/import_tasks.py).

- [src/api/deps.py](../src/api/deps.py) — зависимости FastAPI: получение сессии БД (`get_db_session`), текущего пользователя (`get_current_user`) и администратора (`get_current_admin`). **FR:** FR-7. **Зависимости:** [src/core/database.py](../src/core/database.py), [src/core/models.py](../src/core/models.py), `jose`.

- [src/api/messenger_webhook.py](../src/api/messenger_webhook.py) — универсальный вебхук для мессенджеров (MAX, Telegram, VK). Принимает текстовые и голосовые сообщения, распознаёт речь через Whisper и продолжает диалог после handoff. **FR:** FR-3. **Зависимости:** [src/services/handoff_service.py](../src/services/handoff_service.py), [src/voice/pipeline.py](../src/voice/pipeline.py), [src/services/audio_converter.py](../src/services/audio_converter.py).

- [src/api/telegram_webhook.py](../src/api/telegram_webhook.py) — вебхук для Telegram-бота. **FR:** FR-3. **Зависимости:** [src/bot/telegram.py](../src/bot/telegram.py).

### 4.3. Core-слой (src/core/)

- [src/core/models.py](../src/core/models.py) — все Pydantic-модели данных: `Candidate`, `Campaign`, `InterviewResult`, `ProsodyAnalysis`, `VideoAnalysis`, `User`. Содержит валидацию (`validate_consent`) и метод маскирования PII (`mask_pii`). **FR:** Все. **Зависимости:** `pydantic`.

- [src/core/state.py](../src/core/state.py) — состояние графа LangGraph. Определяет `AgentState` (TypedDict с полями `candidate`, `messages`, `current_step`, `iteration_count`, `requires_human_review`, `interview_result`, `error`) и функцию `should_continue` для conditional edges. **FR:** FR-1…FR-5. **ADR:** ADR-0001 (LangGraph).

- [src/core/metrics.py](../src/core/metrics.py) — Prometheus-метрики приложения: `mrh_candidates_total`, `mrh_pipeline_duration_seconds`, `mrh_fairness_disparate_impact` и другие. **NFR:** NFR-4 (наблюдаемость). **Зависимости:** `prometheus_client`.

- [src/core/audit_logger.py](../src/core/audit_logger.py) — структурированное логирование через `structlog` для аудита (152-ФЗ ст. 18.1). Определяет обязательные поля: `candidate_id`, `action`, `timestamp`, `decision`, `user_id`. **NFR:** NFR-3 (безопасность). **Зависимости:** `structlog`.

- [src/core/logging_config.py](../src/core/logging_config.py) — настройка логирования: JSON-формат, отправка в файл `logs/app.json.log`, интеграция с Filebeat. **NFR:** NFR-4. **Зависимости:** `structlog`.

- [src/core/database.py](../src/core/database.py) — настройка асинхронного SQLAlchemy: создание `async_engine` и `async_session_maker` для работы с PostgreSQL. **Зависимости:** `sqlalchemy`, [src/core/config.py](../src/core/config.py).

### 4.4. PII-слой (src/pii/)

- [src/pii/anonymizer.py](../src/pii/anonymizer.py) — асинхронная обёртка над Microsoft Presidio. Использует `AnalyzerEngine` и `AnonymizerEngine` для маскирования ПДн в тексте. **NFR:** NFR-3 (безопасность). **Зависимости:** `presidio_analyzer`, `presidio_anonymizer`, [src/core/audit_logger.py](../src/core/audit_logger.py).

- [src/pii/recognizers.py](../src/pii/recognizers.py) — четыре кастомных распознавателя для российских форматов: паспорт (`PassportRecognizer`), СНИЛС (`SnilsRecognizer`), телефон (`RussianPhoneRecognizer`), адрес (`RussianAddressRecognizer`). **NFR:** NFR-3. **Зависимости:** `presidio_analyzer`.

### 4.5. Агенты (src/agents/)

- [src/agents/screener/graph.py](../src/agents/screener/graph.py) — граф Agent-Screener: узлы `validate_consent`, `analyze_resume`, `ask_questions`, `evaluate`, `human_review`. **FR:** FR-1. **ADR:** ADR-0001. **Зависимости:** [src/agents/screener/nodes.py](../src/agents/screener/nodes.py), [src/core/state.py](../src/core/state.py).

- [src/agents/screener/nodes.py](../src/agents/screener/nodes.py) — реализация узлов скринера: проверка согласия, анализ резюме, задавание вопросов чек-листа, оценка кандидата, вызов `make_call` и `predict_propensity`. **FR:** FR-1. **Зависимости:** [src/telephony/freeswitch_client.py](../src/telephony/freeswitch_client.py), [src/services/propensity_dialer.py](../src/services/propensity_dialer.py), [src/agents/orchestrator.py](../src/agents/orchestrator.py).

- [src/agents/interviewer/graph.py](../src/agents/interviewer/graph.py) — граф Agent-Interviewer с опциональным видеоанализом. Узлы: `prepare_questions`, `conduct_interview`, `analyze_prosody`, `analyze_video` (опционально), `analyze_results`, `human_review_interview`. **FR:** FR-2. **ADR:** ADR-0001. **Зависимости:** [src/agents/interviewer/nodes.py](../src/agents/interviewer/nodes.py), [src/core/state.py](../src/core/state.py).

- [src/agents/interviewer/nodes.py](../src/agents/interviewer/nodes.py) — реализация узлов интервьюера: генерация вопросов на основе резюме, проведение голосового диалога через `VoicePipeline`, анализ просодии через `librosa`, видеоанализ через DeepFace, формирование итогового скора. **FR:** FR-2. **Зависимости:** [src/voice/pipeline.py](../src/voice/pipeline.py), [src/agents/interviewer/prosody.py](../src/agents/interviewer/prosody.py), [src/agents/interviewer/video_analyzer.py](../src/agents/interviewer/video_analyzer.py).

- [src/agents/coordinator/graph.py](../src/agents/coordinator/graph.py) — граф Agent-Coordinator: узлы `route_candidate`, `screener_node`, `interviewer_node`, `analyst_node`, `handle_handoff`, `analytics_report`, `human_review`. **FR:** FR-3. **ADR:** ADR-0001. **Зависимости:** [src/agents/coordinator/nodes.py](../src/agents/coordinator/nodes.py), [src/core/state.py](../src/core/state.py).

- [src/agents/coordinator/nodes.py](../src/agents/coordinator/nodes.py) — реализация узлов координатора: маршрутизация кандидатов, вызов агентов, handoff через `HandoffService`, отправка сообщений в мессенджеры. **FR:** FR-3. **Зависимости:** [src/services/handoff_service.py](../src/services/handoff_service.py), [src/services/hr_integrations.py](../src/services/hr_integrations.py).

- [src/agents/onboarding/graph.py](../src/agents/onboarding/graph.py) — граф Agent-Onboarding: узлы `collect_documents`, `verify_documents`, `schedule_welcome`, `send_onboarding_package`, `human_review`. **FR:** FR-4. **ADR:** ADR-0001.

- [src/agents/analyst/graph.py](../src/agents/analyst/graph.py) — граф Agent-Analyst: узлы `aggregate_metrics`, `detect_bottlenecks`, `fairness_audit`, `generate_report`, `human_review`. **FR:** FR-5. **ADR:** ADR-0001. **Зависимости:** [src/agents/analyst/fairness_metrics.py](../src/agents/analyst/fairness_metrics.py).

- [src/agents/analyst/fairness_metrics.py](../src/agents/analyst/fairness_metrics.py) — расчёт метрик fairness: `demographic_parity`, `disparate_impact`, `false_rejection_rate`. **FR:** FR-5. **Зависимости:** `pandas` (опционально), `numpy`.

- [src/agents/orchestrator.py](../src/agents/orchestrator.py) — оркестратор кампаний: запускает обработку списка кандидатов через граф скринера. **FR:** FR-1. **Зависимости:** [src/agents/screener/graph.py](../src/agents/screener/graph.py).

### 4.6. Голосовой пайплайн (src/voice/, src/telephony/)

- [src/voice/pipeline.py](../src/voice/pipeline.py) — основной голосовой пайплайн: ASR (Whisper через LiveKit) → обработка → TTS (Silero, пока заглушка). Содержит метод `process_audio` для обработки аудио-фреймов и `run_worker` для запуска LiveKit-воркера. **FR:** FR-1, FR-2. **ADR:** ADR-0004. **Зависимости:** `livekit.agents`, `livekit.plugins.openai`.

- [src/voice/livekit_client.py](../src/voice/livekit_client.py) — клиент для подключения к LiveKit Server: создание комнаты, публикация аудио-трека, отправка и получение аудио. **FR:** FR-1, FR-2. **ADR:** ADR-0004. **Зависимости:** `livekit.api`, `livekit.rtc`.

- [src/telephony/esl_client.py](../src/telephony/esl_client.py) — низкоуровневый асинхронный клиент для FreeSWITCH ESL: подключение, аутентификация, отправка команд API (`originate`, `api`). **FR:** FR-1. **ADR:** ADR-0002. **Зависимости:** `asyncio`.

- [src/telephony/freeswitch_client.py](../src/telephony/freeswitch_client.py) — высокоуровневый клиент для FreeSWITCH: `make_call` (исходящий звонок), `check_call_status` (проверка статуса звонка). **FR:** FR-1. **ADR:** ADR-0002. **Зависимости:** [src/telephony/esl_client.py](../src/telephony/esl_client.py).

### 4.7. Сервисы (src/services/)

- [src/services/propensity_dialer.py](../src/services/propensity_dialer.py) — пропенсити-дайлер на CatBoost: предсказывает вероятность дозвона для кандидата на основе признаков (час, день недели, сегмент и др.). Загружается из MLflow Model Registry или локального файла. **FR:** FR-1. **Зависимости:** `catboost`, `mlflow`.

- [src/services/semantic_cache.py](../src/services/semantic_cache.py) — MVR-кэш для LLM на основе Qdrant. Хранит эмбеддинги запросов и их ответы. Проверяет косинусное сходство ≥0.95, при попадании возвращает кэшированный ответ. **FR:** FR-1, FR-3. **Зависимости:** `qdrant_client`, `sentence-transformers`.

- [src/services/deletion_service.py](../src/services/deletion_service.py) — каскадное удаление данных кандидата (право на забвение): PostgreSQL (soft delete), Qdrant (удаление точек), S3 (аудио), Redis (ключи), Mem0 (эпизодическая память), аудит-логи (soft delete). **NFR:** NFR-3. **Зависимости:** `sqlalchemy`, `qdrant_client`, `redis`, `mem0`.

- [src/services/handoff_service.py](../src/services/handoff_service.py) — сервис для омниканального handoff: сохранение и восстановление состояния диалога в Redis, увеличение счётчика неудачных звонков. **FR:** FR-3. **Зависимости:** `redis`.

- [src/services/hr_integrations.py](../src/services/hr_integrations.py) — интеграции с HR-системами и мессенджерами: отправка сообщений в Telegram, VK, MAX, проверка календарей, анонимизация ПДн. **FR:** FR-3, FR-6. **Зависимости:** `httpx`, `tenacity`.

- [src/services/calendar_service.py](../src/services/calendar_service.py) — интеграция с Google Calendar и Яндекс.Календарём: проверка свободных слотов для HR. **FR:** FR-3. **Зависимости:** `google-api-python-client`, `httpx`.

- [src/services/campaign_service.py](../src/services/campaign_service.py) — CRUD-операции для рекрутинговых кампаний: создание, получение, добавление кандидатов, запуск и завершение. **FR:** FR-7. **Зависимости:** `sqlalchemy`.

- [src/services/import_resumes.py](../src/services/import_resumes.py) — импорт резюме с внешних платформ (hh.ru, Avito) и создание кандидатов. **FR:** FR-6. **Зависимости:** [src/integrations/job_boards.py](../src/integrations/job_boards.py).

- [src/services/model_weights_service.py](../src/services/model_weights_service.py) — управление весами пропенсити-модели: получение и обновление из БД. **FR:** FR-7. **Зависимости:** `sqlalchemy`.

## 5. Code Style и инструменты

### 5.1. Python (backend)

- **Линтер:** Ruff (`ruff check .`). Конфигурация в [pyproject.toml](../pyproject.toml) включает выбор правил: `E`, `F`, `I`, `W`, `N`, `UP`, `B`, `SIM`, `ARG`, `C4`. Line length установлен в 100 символов.
- **Type checker:** Mypy (`mypy . --strict`). Включены строгие проверки, версия Python 3.12.
- **Форматтер:** Ruff (`ruff format .`) — форматирует код в соответствии с Black-подобным стилем.
- **Импорты:** сортируются автоматически через Ruff (встроенная поддержка isort).
- **Докстринги:** рекомендуется использовать Google-style для всех публичных функций и классов.
- **Именование:** переменные и функции — `snake_case`, классы — `PascalCase`, константы — `UPPER_CASE`.

### 5.2. TypeScript (frontend, если разрабатывается)

Правила для фронтенда (React/Vue) следуют стандартным практикам:
- **Линтер:** ESLint (`npm run lint`).
- **Type checker:** `tsc --noEmit`.
- **Форматтер:** Prettier.
- **Именование:** компоненты — `PascalCase`, хуки — `camelCase` с префиксом `use`, файлы — `.tsx` или `.ts`.

### 5.3. Pre-commit хуки

Для автоматической проверки кода перед коммитом используются pre-commit хуки. Установка: `pre-commit install`. Конфигурация в `.pre-commit-config.yaml` включает:
- `ruff check --fix` — исправление ошибок линтинга.
- `mypy .` — проверка типов.
- `pytest -m unit` — прогон unit-тестов.

## 6. Git Flow

### 6.1. Ветки

- **`main`** — production-ветка. Здесь находится стабильная версия, готовая к релизу. Коммиты в `main` только через PR из `develop` или `release/*`.
- **`develop`** — основная ветка разработки. Сюда мержатся все фичи и исправления.
- **`feature/*`** — ветки для новых функций. Создаются от `develop`, после завершения сливаются обратно через PR.
- **`fix/*`** — ветки для исправления багов. Могут создаваться как от `develop`, так и от `main` (для hotfix).
- **`release/*`** — ветки для подготовки релиза. Создаются от `develop`, после тестирования сливаются в `main` и обратно в `develop`.

### 6.2. Соглашение о коммитах (Conventional Commits)

Мы используем стандарт [Conventional Commits](https://www.conventionalcommits.org/):
- **Типы:** `feat` (новая функциональность), `fix` (исправление), `docs` (документация), `refactor` (рефакторинг), `test` (тесты), `chore` (инфраструктура, зависимости).
- **Формат:** `<type>(<scope>): <subject>`
- **Пример:** `feat(screener): add propensity dialer integration`

### 6.3. Pull Request

- Создаётся из `feature/*` или `fix/*` в `develop`.
- В описании PR указывается: что было сделано, зачем, как протестировать.
- Требуется минимум 1 approve от другого разработчика.
- CI-проверки (линтер, typecheck, unit-тесты) должны быть зелёными.
- Слияние выполняется через **squash merge** для поддержания чистой истории.

## 7. Contribution Guide

### 7.1. Как выбрать задачу

- Задачи отмечены в GitHub Issues метками `good first issue` (для новичков) и `help wanted` (для контрибьюторов).
- Перед началом работы напишите комментарий в issue, чтобы избежать дублирования усилий.
- Если вы хотите предложить новую функциональность, создайте issue с меткой `enhancement` и опишите предложение.

### 7.2. Процесс разработки

1. **Создайте ветку:** `git checkout -b feature/FEAT-123-description` или `fix/FIX-123-description`.
2. **Напишите код и тесты:** рекомендуется следовать TDD (Test-Driven Development) — сначала падающий тест, затем реализация, затем рефакторинг.
3. **Запустите pre-commit:** `pre-commit run --all-files`.
4. **Запушите ветку** и создайте Pull Request в `develop`.
5. **Дождитесь CI-проверок** и получите approve от ревьюера.
6. **Смержите PR** (squash merge).

### 7.3. Рекомендации по коду

- **KISS (Keep It Simple, Stupid):** избегайте излишней сложности. Пишите код, понятный другим разработчикам.
- **Async/await:** для всех I/O-операций (запросы к БД, HTTP, Redis, внешние API) используйте асинхронные функции.
- **HTTP-клиент:** используйте `httpx.AsyncClient` с настройкой таймаутов и ретраев через `tenacity`.
- **Секреты:** никогда не хардкодьте ключи и пароли. Все чувствительные данные должны загружаться из переменных окружения через [src/core/config.py](../src/core/config.py).
- **Документация:** публичные функции и классы должны иметь docstring в Google-style.
- **Типизация:** все функции должны быть аннотированы типами (mypy в strict-режиме).

## 8. Архитектурное ревью (сжато)

### 8.1. Общая оценка зрелости

| Измерение | Оценка (1–5) | Комментарий |
|-----------|--------------|-------------|
| **Модульность** | 4.0 | Хорошее разделение на агенты, но есть смешение ответственности в координаторе |
| **Масштабируемость** | 3.5 | K8s + HPA заложены, но не протестированы под реальной нагрузкой >1000 сессий |
| **Безопасность** | 3.0 | PII-защита и аудит есть, но нет полноценного SAST/DAST в CI |
| **Тестируемость** | 3.0 | Unit-тесты покрывают core, но интеграционные и E2E требуют доработки |
| **Наблюдаемость** | 4.0 | Prometheus + Grafana + ELK + Jaeger — полный стек |
| **Сопровождаемость** | 4.5 | Код чистый, есть ADR, документация актуальна |
| **Среднее** | **3.7** | Архитектура зрелая, но требует доработок |

### 8.2. Антипаттерны (кратко)

- **God Object:** [src/agents/coordinator/nodes.py](../src/agents/coordinator/nodes.py) — содержит 7 узлов, выполняющих и маршрутизацию, и бизнес-логику (handoff, analytics). Это нарушает принцип единственной ответственности.
- **Cyclic Dependencies:** обнаружена циклическая зависимость между [src/core/state.py](../src/core/state.py) → [src/core/models.py](../src/core/models.py) → [src/services/hr_integrations.py](../src/services/hr_integrations.py) → [src/pii/anonymizer.py](../src/pii/anonymizer.py) → [src/core/state.py](../src/core/state.py) (частичный цикл через импорты).
- **Tight Coupling:** [src/agents/screener/nodes.py](../src/agents/screener/nodes.py) напрямую вызывает `telephony.make_call` и `propensity_dialer.predict_propensity`, что затрудняет тестирование и замену реализаций.
- **Leaking Abstractions:** [src/core/state.py](../src/core/state.py) определяет `AgentState`, который включает `Candidate` и `InterviewResult` — детали реализации агентов «протекают» в общий core, нарушая инкапсуляцию.

### 8.3. Технический долг (кратко)

| Файл | Строка | Тип | Описание | Приоритет |
|------|--------|-----|----------|-----------|
| [src/agents/onboarding/nodes.py](../src/agents/onboarding/nodes.py) | 45 | TODO | Реализовать реальную интеграцию с 1С через RPA | Critical |
| [src/voice/pipeline.py](../src/voice/pipeline.py) | 112 | FIXME | TTS возвращает заглушку, нужна интеграция с Silero | Critical |
| [src/agents/coordinator/nodes.py](../src/agents/coordinator/nodes.py) | 89 | TODO | Добавить проверку календаря перед назначением собеседования | High |
| `src/api/middleware.py` | 34 | TODO | Реализовать rate limiting | Medium |
| [src/services/deletion_service.py](../src/services/deletion_service.py) | 76 | TODO | Добавить удаление из Mem0 и календарей | Medium |
| [tests/integration/test_analyst_e2e.py](../tests/integration/test_analyst_e2e.py) | 15 | TODO | Добавить тесты для fairness-аудита | Medium |

### 8.4. Рекомендации (сжато)

- **Краткосрочные (T+1 месяц):**
  - Закрыть critical TODOs (интеграция с 1С и Silero TTS).
  - Улучшить покрытие тестами: добавить интеграционные тесты для внешних API.
  - Внедрить SAST (Semgrep) в CI для выявления уязвимостей.
- **Среднесрочные (T+3 месяца):**
  - Внедрить feature flags и API versioning для безопасного развёртывания.
  - Реализовать rate limiting через Redis.
  - Провести рефакторинг координатора: вынести бизнес-логику в отдельные сервисы.
- **Долгосрочные (T+6 месяцев):**
  - Настроить автоскалинг голосового пайплайна на основе нагрузки.
  - Провести шардирование PostgreSQL (партиционирование по дате).
  - Рассмотреть миграцию внутренних вызовов на gRPC для повышения производительности.

## 9. Заключение и взаимосвязь с другими документами

Данный документ предоставляет новый разработчик полный набор инструментов для быстрого старта работы над проектом Multi-Agent Mass Recruitment Hub. Вы узнали, как развернуть систему локально, как устроена структура кода, где находятся ключевые компоненты, как оформлять код, работать с Git и вносить вклад в проект. Архитектурное ревью даёт честную оценку текущего состояния системы и указывает направления для улучшения.

Для более глубокого погружения в отдельные аспекты системы рекомендуем обратиться к следующим документам из нашего пакета спецификаций:

- [SYSTEM_SPECIFICATION_AND_PRODUCT_GUIDE.md](./SYSTEM_SPECIFICATION_AND_PRODUCT_GUIDE.md) — бизнес-контекст, функциональные и нефункциональные требования, продуктовое видение.
- [ARCHITECTURE_AND_DATA_MODEL.md](./ARCHITECTURE_AND_DATA_MODEL.md) — архитектурный фундамент, C4-диаграммы, модель данных PostgreSQL.
- [AI_AGENT_AND_ML_PIPELINE.md](./AI_AGENT_AND_ML_PIPELINE.md) — детальное описание работы AI-агентов, ML-пайплайна и fairness-аудита.
- [VOICE_AND_TELEPHONY_PIPELINE.md](./VOICE_AND_TELEPHONY_PIPELINE.md) — голосовой пайплайн, телефония, ASR/TTS.
- [API_AND_USER_INTERFACE_SPECIFICATION.md](./API_AND_USER_INTERFACE_SPECIFICATION.md) — REST API, WebSocket, UI-экраны и use cases.
- [DEPLOYMENT_OBSERVABILITY_AND_ADMIN_GUIDE.md](./DEPLOYMENT_OBSERVABILITY_AND_ADMIN_GUIDE.md) — развёртывание, CI/CD, мониторинг, администрирование.
- [SECURITY_COMPLIANCE_AND_PRIVACY_GUIDE.md](./SECURITY_COMPLIANCE_AND_PRIVACY_GUIDE.md) — безопасность, PII-архитектура, 152-ФЗ, ФСТЭК.
- [QUALITY_ASSURANCE_AND_TESTING_STRATEGY.md](./QUALITY_ASSURANCE_AND_TESTING_STRATEGY.md) — стратегия тестирования, тест-кейсы, нагрузочные тесты.
