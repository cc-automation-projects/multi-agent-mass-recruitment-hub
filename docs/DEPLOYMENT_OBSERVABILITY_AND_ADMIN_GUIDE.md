# Руководство по развёртыванию, наблюдаемости и администрированию Multi-Agent Mass Recruitment Hub

## 1. Введение в эксплуатацию системы

Эксплуатация Multi-Agent Mass Recruitment Hub требует комплексного подхода, охватывающего как инфраструктурные компоненты (Kubernetes, базы данных, телефонию), так и прикладной уровень (AI-агенты, голосовой пайплайн). Система развёртывается в Yandex Cloud с использованием Managed Kubernetes, что обеспечивает высокую доступность, автоматическое масштабирование и соответствие требованиям ФСТЭК по локализации данных. Вся инфраструктура описывается кодом (Infrastructure as Code) через Terraform и управляется через Helm-чарты, что гарантирует воспроизводимость и упрощает обновления.

Цель данного документа — предоставить исчерпывающее руководство для DevOps-инженеров, SRE и системных администраторов, ответственных за развёртывание, мониторинг, поддержку и развитие системы. Мы последовательно рассмотрим топологию production-окружения, процесс деплоя с нуля, CI/CD пайплайн, инструменты наблюдаемости (метрики, логи, трассировки), административные задачи (управление пользователями, бэкапы, масштабирование) и типовые сценарии устранения неисправностей. Понимание этих аспектов критически важно для обеспечения целевых показателей надёжности (99.9% uptime) и производительности (1000 параллельных голосовых сессий), зафиксированных в NFR.

Документ тесно связан с архитектурными решениями, описанными в **[ARCHITECTURE_AND_DATA_MODEL.md](./ARCHITECTURE_AND_DATA_MODEL.md)**, и опирается на конкретные файлы конфигурации, расположенные в репозитории. Все команды и примеры приведены для production-окружения, но также даны инструкции для локальной разработки с использованием Docker Compose.

## 2. Топология production-окружения

Production-окружение Multi-Agent Mass Recruitment Hub развёрнуто в Yandex Cloud и включает следующие компоненты:

- **Yandex Managed Kubernetes** — контрольная плоскость и рабочие ноды (3 ноды, каждая 8 vCPU, 32 ГБ RAM, SSD-диски). На нодах работают поды приложений, а также системные компоненты (Ingress Controller, cert-manager, External Secrets Operator).
- **Yandex Managed PostgreSQL** — кластер с 2 репликами (primary + replica) для отказоустойчивости, версия 16 с pgvector.
- **Yandex Managed Redis** — кластер (primary + replica) для кэширования, сессий и очередей Celery.
- **Qdrant** — развёрнут внутри K8s как StatefulSet с 4 шардами и 2 репликами на каждый шард для высокой пропускной способности векторного поиска.
- **FreeSWITCH** — StatefulSet из 3 реплик, каждая обслуживает SIP-звонки (порт 5060 UDP/TCP), ESL (8021 TCP) и WebRTC (7443 TCP).
- **LiveKit Server** — Deployment с 2 репликами, управляет WebRTC-сессиями (порты 7880, 7881, 7882).
- **Приложения** — API Gateway (FastAPI) с 3 репликами, Celery Workers (масштабируются HPA), Celery Beat (1 реплика), Flower для мониторинга задач (1 реплика).
- **Мониторинг** — Prometheus (1 реплика с retention 15 дней), Grafana (1 реплика), Alertmanager (1 реплика).
- **Логи** — ELK Stack: Elasticsearch (3 реплики), Logstash (2 реплики), Kibana (1 реплика).
- **Балансировка трафика** — Yandex Application Load Balancer (ALB) для внешнего доступа к API и WebSocket, а также NGINX Ingress Controller внутри K8s для маршрутизации HTTP/HTTPS.
- **Хранилище артефактов** — Yandex Object Storage (S3-совместимое) для аудиозаписей, бэкапов и артефактов MLflow.

Диаграмма топологии (Mermaid):

```mermaid
flowchart TB
    subgraph "Yandex Cloud"
        subgraph "VPC"
            subgraph "Managed K8s Cluster"
                subgraph "Ingress"
                    NGINX[NGINX Ingress Controller]
                end
                subgraph "Applications"
                    API[API Gateway (FastAPI) - 3 реплики]
                    WORKER[Celery Workers - HPA]
                    BEAT[Celery Beat]
                    FLOWER[Flower]
                    LK[LiveKit - 2 реплики]
                    FS[FreeSWITCH - 3 реплики (StatefulSet)]
                    QDRANT[Qdrant - 4 шарда × 2 реплики]
                end
                subgraph "Monitoring & Logging"
                    PROM[Prometheus]
                    GRAF[Grafana]
                    ALERT[Alertmanager]
                    ELASTIC[Elasticsearch]
                    LOGSTASH[Logstash]
                    KIBANA[Kibana]
                end
            end
            subgraph "Managed Services"
                PG[(PostgreSQL Cluster)]
                REDIS[(Redis Cluster)]
                S3[(Object Storage)]
            end
        end
        ALB[Yandex ALB]
    end

    ALB --> NGINX
    NGINX --> API
    NGINX --> LK
    NGINX --> FS

    API --> PG
    API --> REDIS
    API --> QDRANT
    API --> S3
    WORKER --> PG
    WORKER --> REDIS
    WORKER --> QDRANT
    WORKER --> S3

    API --> PROM
    WORKER --> PROM
    PROM --> GRAF
    PROM --> ALERT

    API --> LOGSTASH
    WORKER --> LOGSTASH
    LOGSTASH --> ELASTIC
    ELASTIC --> KIBANA
```

**Взаимодействие компонентов:**

- Внешний трафик поступает через Yandex ALB, который направляет HTTPS-запросы на NGINX Ingress. Ingress маршрутизирует запросы к сервисам API, LiveKit и FreeSWITCH в зависимости от пути и порта.
- API Gateway обрабатывает REST-запросы, WebSocket-соединения для голоса и вебхуки. Он обращается к PostgreSQL для чтения/записи данных кандидатов, кампаний, результатов; к Redis для сессий и кэша; к Qdrant для семантического кэша и RAG.
- Celery Workers выполняют фоновые задачи (транскрипция, AI-агенты, запись в CRM) и также используют PostgreSQL, Redis, Qdrant, S3.
- FreeSWITCH принимает SIP-вызовы, транскодирует аудио и передаёт его в LiveKit через WebRTC-мост. LiveKit управляет комнатами и агентами, взаимодействует с ASR/TTS.
- Мониторинг и логи собираются со всех подов и отправляются в Prometheus и ELK соответственно.

Отказоустойчивость достигается за счёт репликации баз данных, множественных реплик приложений, анти-аффинити правил в K8s и автоматического перезапуска сбойных подов.

## 3. Развёртывание (Deployment)

### 3.1. Предварительные требования

Перед началом развёртывания необходимо убедиться, что выполнены следующие условия:

- Учётная запись Yandex Cloud с активным платёжным аккаунтом и достаточными правами для создания ресурсов (роль `editor` или выше).
- Установленные на локальной машине инструменты:
  - `yc` (Yandex Cloud CLI) — авторизован и настроен на нужный каталог.
  - `kubectl` — версия 1.28+.
  - `helm` — версия 3.9+.
  - `terraform` — версия 1.5+.
  - `docker` — для сборки образов.
- Зарегистрированный SIP-транк у внешнего провайдера для исходящих звонков (или тестовый SIP-сервер).
- Домен (например, `Multi-Agent Mass Recruitment Hub.ru`) с делегированными NS-записями на Yandex Cloud DNS (или другой DNS-провайдер).
- Wildcard TLS-сертификат (можно получить через Let's Encrypt с помощью cert-manager).
- Docker registry: Yandex Container Registry (рекомендуется) или другой, доступный из K8s.

### 3.2. Подготовка инфраструктуры (Terraform)

Инфраструктура описывается в `[infra/terraform/main.tf](../infra/terraform/main.tf)`. Этот файл создаёт:

- VPC с подсетями в трёх зонах доступности.
- Managed Kubernetes кластер (региональный, с 3 мастер-нодами).
- Managed PostgreSQL кластер (версия 16, 2 реплики).
- Managed Redis кластер (версия 7.2, 2 реплики).
- Object Storage бакет для аудио и бэкапов.

Перед применением необходимо создать файл `production.tfvars` с реальными значениями переменных (cloud_id, folder_id, zone, db_user, db_password, redis_password и т.д.).

Пример команды для применения:

```bash
cd infra/terraform
terraform init
terraform plan -var-file=production.tfvars
terraform apply -auto-approve -var-file=production.tfvars
```

После успешного выполнения Terraform выведет IP-адреса и имена кластеров, которые понадобятся на следующих этапах (например, для настройки DNS и подключения к БД).

### 3.3. Настройка DNS и TLS

1. Создайте DNS-зону в Yandex Cloud DNS или используйте внешнего провайдера. Добавьте A-запись для `api.Multi-Agent Mass Recruitment Hub.ru` и `ws.Multi-Agent Mass Recruitment Hub.ru`, указав внешний IP-адрес Ingress-контроллера (который будет назначен после установки NGINX Ingress).
2. Установите cert-manager для автоматического получения TLS-сертификатов:
   ```bash
   helm repo add jetstack https://charts.jetstack.io
   helm repo update
   helm install cert-manager jetstack/cert-manager --namespace cert-manager --create-namespace --set installCRDs=true
   ```
3. Создайте ClusterIssuer для Let's Encrypt (файл `cluster-issuer.yaml`):
   ```yaml
   apiVersion: cert-manager.io/v1
   kind: ClusterIssuer
   metadata:
     name: letsencrypt-prod
   spec:
     acme:
       server: https://acme-v02.api.letsencrypt.org/directory
       email: admin@Multi-Agent Mass Recruitment Hub.ru
       privateKeySecretRef:
         name: letsencrypt-prod
       solvers:
         - http01:
             ingress:
               class: nginx
   ```
   Примените: `kubectl apply -f cluster-issuer.yaml`.
4. Установите NGINX Ingress Controller через Helm:
   ```bash
   helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
   helm repo update
   helm install ingress-nginx ingress-nginx/ingress-nginx --namespace ingress-nginx --create-namespace
   ```

После установки получите внешний IP Ingress-контроллера: `kubectl get svc -n ingress-nginx`. Обновите A-запись в DNS соответствующим образом.

### 3.4. Развёртывание баз данных

Базы данных уже созданы Terraform. Необходимо получить строки подключения:

- PostgreSQL: хост, порт (обычно 6432 для Managed PostgreSQL с балансировщиком), база, пользователь, пароль. Эти данные хранятся в секретах Yandex Cloud (можно извлечь через `yc managed-postgresql cluster get`).
- Redis: хост, порт, пароль (если включён).

Эти параметры будут переданы в приложение через секреты Kubernetes (см. раздел 3.5).

Qdrant развёртывается внутри кластера K8s с помощью Helm-чарта:

```bash
helm repo add qdrant https://qdrant.github.io/qdrant-helm
helm repo update
helm install mrh-qdrant qdrant/qdrant -n mass-recruit-hub --create-namespace \
  --set replicaCount=4 \
  --set persistence.size=100Gi \
  --set resources.requests.cpu=4 \
  --set resources.requests.memory=16Gi \
  --set config.service.grpcPort=6334
```

При необходимости можно настроить параметры HNSW и другие через `--set config.storage.optimizers...`.

### 3.5. Развёртывание приложения (Helm)

Основной Helm-чарт находится в `infra/helm/mass-recruit-hub/`. Он содержит шаблоны для всех компонентов приложения: API, Celery workers, Beat, Flower, Ingress, ServiceMonitor, ExternalSecret и др.

Перед установкой необходимо создать namespace и секреты:

```bash
kubectl create namespace mass-recruit-hub
```

Секреты можно создать вручную (для dev) или через External Secrets Operator (для production). В production рекомендуется использовать External Secrets с интеграцией с Yandex Lockbox (или HashiCorp Vault). Чарт включает шаблон `external[secret.yaml](../infra/helm/mass-recruit-hub/templates/secret.yaml)`, который связывается с SecretStore, указывающим на Lockbox.

Для тестового развёртывания можно создать секрет напрямую:

```bash
kubectl create secret generic mass-recruit-hub-secrets -n mass-recruit-hub \
  --from-literal=LLM_API_KEY=... \
  --from-literal=DATABASE_URL=postgresql://user:pass@host:6432/Multi-Agent Mass Recruitment Hub \
  --from-literal=REDIS_URL=redis://:pass@host:6380/0 \
  --from-literal=FREESWITCH_PASSWORD=ClueCon \
  --from-literal=LIVEKIT_API_SECRET=dev_secret \
  --from-literal=JWT_SECRET_KEY=strong-secret
```

После подготовки секретов выполните установку чарта:

```bash
helm upgrade --install mass-recruit-hub ./infra/helm/mass-recruit-hub \
  -n mass-recruit-hub \
  -f ./infra/helm/mass-recruit-hub/values-prod.yaml \
  --set image.tag=latest
```

В `[values-prod.yaml](../infra/helm/mass-recruit-hub/values-prod.yaml)` уже заданы production-настройки: количество реплик, HPA, ресурсы, анти-аффинити, параметры автокаслейтинга. При необходимости можно переопределить их через `--set`.

Проверьте статус деплоя:

```bash
kubectl rollout status deployment/mass-recruit-hub-api -n mass-recruit-hub
kubectl get pods -n mass-recruit-hub
```

### 3.6. Развёртывание FreeSWITCH

FreeSWITCH разворачивается как StatefulSet с 3 репликами. Конфигурация описана в `infra/helm/mass-recruit-hub/templates/freeswitch-statefulset.yaml`. Для него монтируются конфигурационные файлы из `infra/docker/freeswitch/conf/`. ESL-конфиг (`[event_socket.conf.xml](../infra/docker/freeswitch/conf/autoload_configs/event_socket.conf.xml)`) уже настроен на порт 8021 с паролем, который передаётся через секрет.

После установки чарта FreeSWITCH будет доступен внутри кластера по сервису `freeswitch` на портах 5060 (SIP), 8021 (ESL), 7443 (WebRTC). Для внешних SIP-вызовов необходимо настроить балансировку через Yandex ALB или использовать NodePort и статический IP.

Балансировка SIP-трафика осуществляется через DNS SRV-записи или через внешний SIP-прокси (например, OpenSIPS). В текущей реализации для простоты используется round-robin через Ingress (но для SIP требуется специальная настройка). Рекомендуется использовать отдельный балансировщик с поддержкой SIP (например, Yandex ALB с протоколом UDP).

### 3.7. Dev-окружение (Docker Compose)

Для локальной разработки и тестирования предусмотрен `[docker-compose.yml](../docker-compose.yml)`, который поднимает все необходимые сервисы:

- PostgreSQL, Redis, Qdrant (в режиме standalone)
- FreeSWITCH, LiveKit
- Приложение (с hot-reload через `[Dockerfile.dev](../Dockerfile.dev)`)
- MLflow, ELK (Elasticsearch, Logstash, Kibana), Prometheus, Grafana

Запуск:

```bash
docker-compose up -d
docker-compose exec app alembic upgrade head
docker-compose exec app python scripts/load_demo_data.py   # если есть
```

После запуска доступны:
- API: http://localhost:8000
- Grafana: http://localhost:3000 (admin/admin)
- Kibana: http://localhost:5601
- Flower: http://localhost:5555

Для остановки: `docker-compose down`.

## 4. CI/CD Pipeline (GitHub Actions)

CI/CD пайплайн автоматизирует сборку, тестирование и деплой приложения при каждом изменении кода. Конфигурация находится в `.github/workflows/ci.yml`.

### 4.1. Общая архитектура пайплайна

Пайплайн запускается при следующих событиях:
- push в ветки `main` и `develop`
- pull request в `main`
- создание тега вида `v*` (релиз)
- ручной запуск (workflow_dispatch) с выбором окружения и тега образа

Этапы (выполняются последовательно):

1. **Линтинг** — проверка стиля кода и типов через `ruff` и `mypy`.
2. **Тестирование** — запуск всех тестов (`pytest` с покрытием), включая unit, интеграционные и e2e.
3. **Сборка Docker-образа** — на основе `[Dockerfile](../Dockerfile)` (multi-stage) с тегом, соответствующим коммиту или тегу.
4. **Публикация в Yandex Container Registry** — аутентификация через YC CLI и push образа.
5. **Деплой в Kubernetes** — выполнение `helm upgrade --install` с новым образом (для staging или production в зависимости от ветки).

Диаграмма CI/CD (Mermaid):

```mermaid
flowchart LR
    Push[Push/PR] --> Lint[Линтинг: ruff, mypy]
    Lint --> Test[Тесты: pytest --cov]
    Test --> Build[Сборка Docker образа]
    Build --> PushCR[Push в Yandex CR]
    PushCR --> Deploy[Helm upgrade --install]
    Deploy --> Rollout[Проверка rollout status]
    Rollout --> Notify[Уведомление в Telegram]
```

### 4.2. Конфигурация (`.github/workflows/ci.yml`)

Содержимое файла включает:

- **Переменные окружения:** `REGISTRY`, `BACKEND_IMAGE`, `FRONTEND_IMAGE` (если есть), `TAG` (по умолчанию `github.sha`).
- **Шаги:**
  - Установка Python и зависимостей (через `pip install -e .[dev]`).
  - Запуск `ruff check .` и `mypy src/`.
  - Запуск тестов: `pytest tests/ -v --cov=src --cov-report=xml`.
  - Сборка Docker: `docker build -t ${{ env.REGISTRY }}/${{ env.BACKEND_IMAGE }}:${{ env.TAG }} .`
  - Пуш: `docker push ${{ env.REGISTRY }}/${{ env.BACKEND_IMAGE }}:${{ env.TAG }}`.
  - Деплой: `helm upgrade --install mass-recruit-hub ./infra/helm/mass-recruit-hub -n mass-recruit-hub -f [values-prod.yaml](../infra/helm/mass-recruit-hub/values-prod.yaml) --set image.tag=${{ env.TAG }}` (для production) или `values-staging.yaml` для staging.

**Секреты GitHub:** необходимо добавить:
- `YC_OAUTH_TOKEN` — для аутентификации в Yandex Cloud.
- `CR_PASSWORD` (если используется другой registry).
- `TELEGRAM_BOT_TOKEN` и `TELEGRAM_CHAT_ID` для уведомлений.

### 4.3. Переменные и секреты

Переменные и секреты хранятся в GitHub Secrets и в `values-*.yaml`. Для production рекомендуется использовать External Secrets Operator, который подтягивает чувствительные данные из Yandex Lockbox, чтобы они не хранились в репозитории.

### 4.4. Ручной запуск и отладка

- **workflow_dispatch:** позволяет вручную запустить деплой с выбором окружения и тега образа. Это полезно для срочных исправлений или кастомных сборок.
- **Откат (Rollback):** в случае неудачного деплоя можно выполнить `helm rollback mass-recruit-hub -n mass-recruit-hub <revision>` или перезапустить деплой с предыдущим тегом через workflow_dispatch.

## 5. Наблюдаемость (Observability)

Наблюдаемость построена на трёх столпах: логи, метрики и трассировки. Все компоненты интегрированы в единую систему мониторинга, что позволяет быстро выявлять и диагностировать проблемы.

### 5.1. Три столпа наблюдаемости

- **Логи:** структурированные JSON-логи через `structlog` с обязательными полями для аудита. Собираются Filebeat, передаются в Logstash для парсинга и маскирования PII, затем индексируются в Elasticsearch. В Kibana построены дашборды для поиска по логам и визуализации.
- **Метрики:** экспортируются приложением на эндпоинте `/metrics` в формате Prometheus. Prometheus собирает их с заданным интервалом и сохраняет в TSDB. На основе метрик строятся алерты и графики в Grafana.
- **Трассировки:** для отслеживания запросов через распределённую систему используется OpenTelemetry с экспортом в Jaeger. Это позволяет увидеть задержки на каждом этапе (ASR, LLM, TTS, запись в БД) и оптимизировать узкие места.

### 5.2. Метрики Prometheus (`[src/core/metrics.py](../src/core/metrics.py)`)

Приложение экспортирует множество кастомных метрик, которые позволяют отслеживать бизнес-показатели и техническое состояние. Ниже приведена полная таблица (в коде они определены в `[src/core/metrics.py](../src/core/metrics.py)`):

| Имя метрики | Тип | Лейблы | Описание |
|-------------|-----|--------|----------|
| `mrh_candidates_total` | Counter | `status`, `source` | Общее количество обработанных кандидатов (по статусу и источнику) |
| `mrh_pipeline_duration_seconds` | Histogram | `agent_stage` | Длительность каждого этапа пайплайна (ASR, LLM, TTS и т.д.) |
| `mrh_queue_depth` | Gauge | `queue_name` | Текущая глубина очередей (Celery, Redis) |
| `mrh_human_review_required_total` | Counter | `stage` | Количество кандидатов, отправленных на ручной просмотр |
| `mrh_screener_questions_total` | Counter | – | Суммарное количество вопросов, заданных скринером |
| `mrh_interviewer_sessions_total` | Counter | `outcome` | Количество проведённых интервью с разбивкой по результату (`conducted`, `passed`, `failed`) |
| `mrh_interviewer_audio_duration_seconds` | Histogram | – | Длительность аудиозаписей интервью (для оценки нагрузки на S3) |
| `mrh_propensity_score` | Gauge | `model_version` | Текущий предсказанный скор пропенсити (средний по всем запросам) |
| `mrh_fairness_disparate_impact` | Gauge | `group` | Значение Disparate Impact для каждой группы (пол, регион и т.д.) |
| `mrh_fairness_demographic_parity` | Gauge | – | Demographic Parity (разница в вероятностях) |
| `mrh_fairness_false_rejection_rate` | Gauge | `group` | Доля ложных отказов по группам |
| `mrh_semantic_cache_hits_total` | Counter | – | Количество попаданий в семантический кэш LLM |
| `mrh_semantic_cache_misses_total` | Counter | – | Количество промахов |
| `mrh_deletion_requests_total` | Counter | `status` | Запросы на удаление данных (право на забвение), статус `accepted`, `failed` |
| `mrh_llm_latency_milliseconds` | Histogram | – | Задержка LLM-инференса (мс) |
| `mrh_llm_router_fallback_total` | Counter | `target` | Количество переключений на fallback-провайдера (YandexGPT, GigaChat) |
| `mrh_integration_requests_total` | Counter | `platform` | Количество вызовов внешних API (hh, Avito, Telegram, etc.) |
| `mrh_integration_errors_total` | Counter | `platform`, `error_type` | Количество ошибок при вызовах внешних API (с кодом ошибки) |

Все метрики собираются с интервалом 15 секунд и доступны для построения графиков в Grafana.

### 5.3. Аудит-лог (structlog) — `[src/core/audit_logger.py](../src/core/audit_logger.py)`

Аудит-лог является обязательным требованием 152-ФЗ. Все действия, связанные с персональными данными, фиксируются в структурированном JSON-формате. Поля:

- `candidate_id` (обязательное)
- `action` (обязательное) — например, `screening_started`, `consent_given`, `call_made`, `decision_made`.
- `timestamp` (ISO8601)
- `decision` (если применимо) — `passed`, `rejected`, `needs_human_review`.
- `user_id` (инициатор, или `system`)
- `session_id`, `campaign_id`, `agent_id`, `duration_ms`, `error` — опционально.

Логи пишутся в файл `logs/app.json.log` (в контейнере) и забираются Filebeat. В Logstash происходит парсинг и маскирование PII (удаляются поля с именами, телефонами), после чего логи индексируются в Elasticsearch с индексом `mrh-audit-{YYYY-MM-DD}`. Retention: 3 года on-line, затем архивация в S3.

### 5.4. Health Checks (`[src/main.py](../src/main.py)`)

В приложении реализованы следующие эндпоинты для проверки работоспособности:

- `GET /health` — общий статус (возвращает `{"status": "healthy", "version": "0.2.0"}`).
- `GET /health/live` — liveness probe (проверяет, что процесс жив, всегда 200 OK).
- `GET /health/ready` — readiness probe (проверяет доступность зависимостей: PostgreSQL, Redis, Qdrant, LLM). Если хотя бы один компонент недоступен, возвращает 503.
- `GET /health/startup` — startup probe (проверяет, завершены ли миграции; используется для отсрочки первых запросов).

Эти эндпоинты используются в Kubernetes для управления жизненным циклом подов.

### 5.5. Grafana Dashboards

Grafana предустановлена с несколькими дашбордами, конфигурация которых лежит в `[infra/grafana/dashboard-mass-recruit-hub.json](../infra/grafana/dashboard-mass-recruit-hub.json)`. Основные панели:

- **Production Overview:** RPS, средняя латентность, уровень ошибок, глубина очередей, количество активных звонков.
- **Voice Pipeline:** график задержек ASR→LLM→TTS, WER, количество звонков, успешность вызовов.
- **AI Agents:** активные кампании, проходной процент по этапам, результаты fairness-аудита.
- **Business KPIs:** Cost-per-Hire, Time-to-Hire, конверсия из отклика в найм.
- **Integrations:** статус вызовов к hh.ru, Avito, Telegram и другим, ошибки по платформам.
- **Compliance/Audit:** панель для поиска по аудит-логам (через Elasticsearch datasource).

Датасорс Prometheus настроен в `[infra/grafana/datasource.yaml](../infra/grafana/datasource.yaml)`.

### 5.6. Alerting (Alertmanager)

Правила алертов описаны в `[infra/prometheus/alerts.yaml](../infra/prometheus/alerts.yaml)`. Они включают:

- `HighWER` — если WER >8% в течение 5 минут (warning).
- `HighLatency` — если P95 latency >3 с для голосового ответа (critical).
- `FairnessViolation` — если Disparate Impact <0.8 (warning).
- `HighFalseRejectionRate` — если FRR >2% (warning).
- `CampaignQueueTooLong` — если глубина очереди кампаний >100 (warning).
- `HighErrorRate` — если общий error rate >5% в течение 2 минут (critical).

Алерты отправляются в Telegram (для warning) и в Telegram + Email + PagerDuty (для critical). Конфигурация Alertmanager находится в отдельном ConfigMap (не показана, но может быть добавлена).

### 5.7. ELK Stack

- **Filebeat** (`[infra/filebeat/filebeat.yml](../infra/filebeat/filebeat.yml)`) установлен как DaemonSet в K8s или как sidecar-контейнер. Он собирает логи из всех подов (пути `/var/log/containers/*.log`) и отправляет их в Logstash.
- **Logstash** (`[infra/elk/logstash.conf](../infra/elk/logstash.conf)`) принимает логи по протоколу Beats, парсит JSON, маскирует PII с помощью регулярных выражений или плагина (например, `prune`), и отправляет в Elasticsearch.
- **Elasticsearch** хранит логи с политикой ILM: горячий (3 дня), тёплый (90 дней), холодный (архив в S3). Индексы создаются по дням.
- **Kibana** предоставляет интерфейс для поиска, визуализации и построения дашбордов.

## 6. Руководство администратора

В этом разделе собраны типовые задачи, которые выполняет системный администратор для поддержания системы в рабочем состоянии.

### 6.1. Управление пользователями и доступом

Управление пользователями осуществляется через таблицу `users` в PostgreSQL. Роли: `admin`, `hr`, `supervisor`. Права проверяются в `[src/api/deps.py](../src/api/deps.py)` (функции `get_current_user` и `get_current_admin`).

Для добавления нового пользователя можно использовать API-эндпоинт `POST /auth/register` (если он открыт) или напрямую через БД:

```sql
INSERT INTO users (id, username, email, hashed_password, role, is_active)
VALUES (gen_random_uuid(), 'new_hr', 'hr@company.ru', '<bcrypt_hash>', 'hr', true);
```

Хеш пароля можно сгенерировать с помощью `passlib` (как в `[src/api/auth.py](../src/api/auth.py)`).

Для изменения роли или блокировки пользователя:

```sql
UPDATE users SET role = 'supervisor', is_active = false WHERE username = 'old_hr';
```

JWT-токены имеют ограниченное время жизни (15 минут для access, 7 дней для refresh). При необходимости можно изменить параметры в `[src/core/config.py](../src/core/config.py)`.

### 6.2. Управление конфигурацией

Все настройки приложения задаются через переменные окружения (полный список в `.[env.example](../env.example)`). В production они передаются через Kubernetes Secrets или External Secrets Operator.

Обновление конфигурации без пересборки образа:

1. Изменить значение в секрете (например, `kubectl edit secret mass-recruit-hub-secrets -n mass-recruit-hub`).
2. Перезапустить поды: `kubectl rollout restart deployment/mass-recruit-hub-api -n mass-recruit-hub`.

Если используется External Secrets, изменение в Lockbox автоматически синхронизируется, и поды перезапускаются через reloader или после перезапуска вручную.

### 6.3. Резервное копирование и восстановление (DR)

**Политика бэкапов:**

- **PostgreSQL:** ежедневный полный дамп (pg_dump) с retention 30 дней, а также непрерывное архивирование WAL (через WAL-G) для Point-in-Time Recovery (PITR) с retention 7 дней. Бэкапы хранятся в S3.
- **Qdrant:** снапшоты каждые 6 часов, хранятся в S3 (retention 14 дней).
- **Аудиозаписи (S3):** версионирование включено, хранение 1 год, затем архивация в Glacier.
- **Логи (ELK):** ILM-политика: горячий (3 дня), тёплый (90 дней), холодный (архив в S3). Для аудит-логов retention 3 года.

**RTO (Recovery Time Objective):** <4 часа. **RPO (Recovery Point Objective):** <1 час (для PostgreSQL — до последнего WAL).

**Playbook восстановления после катастрофы:**

1. Восстановить инфраструктуру через Terraform (запустить `terraform apply` в пустом каталоге).
2. Установить базовые компоненты (cert-manager, ingress, External Secrets).
3. Восстановить PostgreSQL из последнего полного бэкапа + накатить WAL до нужного момента времени (с использованием WAL-G).
4. Восстановить Qdrant из последнего снапшота.
5. Развернуть приложения через Helm (как в разделе 3.5).
6. Проверить работоспособность: `curl https://api.Multi-Agent Mass Recruitment Hub.ru/health`, проверить логи, метрики.

### 6.4. Масштабирование

**Горизонтальное масштабирование (автоматическое):**
- Для API и Celery Workers настроены HPA в `[values-prod.yaml](../infra/helm/mass-recruit-hub/values-prod.yaml)`:
  - API: по CPU (>70%) и памяти (>80%).
  - Celery Workers: по длине очереди (Redis `llen celery` >500) — можно реализовать через custom metric.
- LiveKit: по CPU (>70%).
- FreeSWITCH: StatefulSet с фиксированным числом реплик (3), масштабирование требует изменения конфигурации балансировщика.

**Вертикальное масштабирование:** увеличение ресурсов для баз данных (RAM, CPU) и для приложений через изменение `resources.limits` в values.

**Масштабирование очередей:** при росте числа задач можно увеличить количество воркеров (через HPA или вручную).

### 6.5. Обновление и патчинг

- **Обновление кода:** `git pull` → сборка нового образа → `helm upgrade` с новым тегом. Rolling update гарантирует, что старые поды будут заменяться постепенно.
- **Откат:** `helm rollback mass-recruit-hub -n mass-recruit-hub <номер ревизии>`. Номер ревизии можно узнать через `helm history`.
- **Миграции БД:** выполняются автоматически при старте пода через init-контейнер или как отдельный Job перед деплоем. В `[scripts/deploy-prod.sh](../scripts/deploy-prod.sh)` это делается отдельной командой `kubectl run db-migrate ...`.

## 7. Руководство по устранению неисправностей (Runbook/Troubleshooting)

В этом разделе приведены типовые проблемы, их симптомы, диагностика и способы решения.

### 7.1. Общие принципы диагностики

- **Логи:** используйте `kubectl logs -f <pod>` или `docker compose logs -f <service>`.
- **Метрики:** смотрите дашборды Grafana или делайте прямые запросы к Prometheus.
- **Статус:** `kubectl get pods`, `kubectl describe pod <pod>` для выявления ошибок запуска.
- **Сеть:** проверьте доступность сервисов через `kubectl exec -it <pod> -- curl http://service:port/health`.

### 7.2. Типовые проблемы и их решение

| Проблема | Симптомы | Диагностика | Решение |
|----------|----------|-------------|---------|
| **Backend не стартует** | Контейнер падает (CrashLoopBackOff) | `kubectl logs backend` | Проверить переменные окружения: `DATABASE_URL`, `REDIS_URL`. Убедиться, что БД доступна. Проверить миграции (`alembic current`). |
| **Webhook возвращает 401** | АТС отправляет запрос, получает 401 | Проверить лог API: `kubectl logs backend \| grep webhook` | Синхронизировать `ATS_WEBHOOK_SECRET` в секретах с настройками АТС. |
| **Транскрипция зависла** | Статус звонка "transcribing" >1 минуты | Логи Celery worker (`kubectl logs celery-worker`) | Проверить доступность `audio_url` (S3). Проверить ключи к SpeechKit/Whisper. Увеличить таймауты. |
| **AI-агент не отвечает** | Статус "analyzing" слишком долго | Логи agent_worker | Проверить LLM-эндпоинт (vLLM или YandexGPT). Проверить API-ключи. При недоступности переключиться на fallback. |
| **CRM не пишет** | Статус "writing_crm" → "failed" | Логи crm_writer_worker | Проверить `BITRIX24_WEBHOOK_URL` и права доступа. Проверить, что `deal_id` существует. В случае ошибки выполнить ручной экспорт через API. |
| **WebSocket не подключается** | UI показывает ошибку подключения | Консоль браузера (F12), логи backend | Проверить JWT-токен (не истёк ли). Проверить CORS настройки. Убедиться, что Ingress правильно проксирует WebSocket (аннотация `nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"`). |
| **Очереди растут** | Глубина очереди >1000 | `kubectl exec -it redis-0 -- redis-cli LLEN celery:call_processing` | Добавить реплики Celery worker (`kubectl scale deployment/mass-recruit-hub-celery-worker --replicas=10`). Проверить, что задачи не зависают. |
| **PostgreSQL недоступна** | Healthcheck падает | `kubectl logs postgres-0` | Проверить диск (если переполнен). Проверить WAL. Восстановить из бэкапа, если база повреждена. |
| **Redis OOM (Out of Memory)** | Ошибки в логах Redis | `kubectl exec -it redis-0 -- redis-cli INFO memory` | Увеличить `maxmemory` в конфиге Redis. Очистить неиспользуемые ключи (например, сессии, истекшие кэши). Перезапустить Redis. |
| **Высокая задержка** | P95 latency >3 с | График latency в Grafana | Увеличить ресурсы (CPU/RAM) для API и Celery. Оптимизировать запросы к БД (индексы). Включить кэширование. Добавить реплики. |
| **FreeSWITCH не принимает звонки** | Звонок не устанавливается | Логи FreeSWITCH (`kubectl logs freeswitch-0`) | Проверить, что SIP-транк зарегистрирован (команда `sofia status`). Проверить сетевые правила (порты 5060/8021 открыты). |
| **LiveKit не подключается** | Ошибка в логах LiveKit | `kubectl logs livekit-0` | Проверить WebRTC-порты (7880, 7881, 7882). Убедиться, что IP адрес доступен извне. Проверить секреты (API_KEY/API_SECRET). |

### 7.3. Полезные команды для диагностики

```bash
# Логи всех подов в namespace
kubectl logs -f -n mass-recruit-hub --all-containers

# Логи конкретного пода
kubectl logs -f deployment/mass-recruit-hub-api -n mass-recruit-hub

# Статус всех подов
kubectl get pods -n mass-recruit-hub

# Вход в контейнер для отладки
kubectl exec -it deployment/mass-recruit-hub-api -- /bin/bash

# Проверка очередей Celery (через Redis)
kubectl exec -it redis-0 -n mass-recruit-hub -- redis-cli LLEN celery:call_processing

# Проверка здоровья API
curl https://api.Multi-Agent Mass Recruitment Hub.ru/health

# Проверка подключения к БД из пода
kubectl exec -it deployment/mass-recruit-hub-api -- python -c "from src.core.database import engine; import asyncio; asyncio.run(engine.connect())"

# Получение логов FreeSWITCH
kubectl logs -f statefulset/freeswitch -n mass-recruit-hub

# Перезапуск всех подов (для применения новых конфигураций)
kubectl rollout restart deployment/mass-recruit-hub-api -n mass-recruit-hub
```

## 8. Заключение и взаимосвязь с другими документами

Данное руководство охватывает все аспекты эксплуатации Multi-Agent Mass Recruitment Hub: от развёртывания инфраструктуры и приложений до мониторинга, администрирования и устранения неисправностей. Инфраструктура построена на лучших практиках облачной инженерии: Infrastructure as Code, GitOps, автоматическое масштабирование, отказоустойчивость и полная наблюдаемость. Это позволяет обеспечить целевые показатели NFR (99.9% uptime, поддержка 1000 параллельных сессий) и быстро реагировать на любые инциденты.

Документ тесно связан со следующими артефактами:
- **[SYSTEM_SPECIFICATION_AND_PRODUCT_GUIDE.md](./SYSTEM_SPECIFICATION_AND_PRODUCT_GUIDE.md)** — бизнес-требования и NFR, которые мы реализуем через инфраструктуру.
- **[ARCHITECTURE_AND_DATA_MODEL.md](./ARCHITECTURE_AND_DATA_MODEL.md)** — архитектурный фундамент, модель данных, C4-диаграммы.
- **[API_AND_USER_INTERFACE_SPECIFICATION.md](./API_AND_USER_INTERFACE_SPECIFICATION.md)** — описание API, которое мы разворачиваем и мониторим.

Все команды и конфигурации основаны на реальных файлах из репозитория, что гарантирует соответствие документации текущему коду. Система готова к промышленной эксплуатации и дальнейшему развитию.
