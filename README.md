# AircraftIQ — Aircraft Intelligence Dashboard

> **Language / 언어**: [English](#english) · [한국어](#한국어)

---

<a name="english"></a>
## English

A web dashboard that analyzes aircraft Non-Routine (NR) maintenance records using AI.  
Built on Google ADK + Gemini 2.5 Flash + BigQuery — query and visualize maintenance data through natural language.

---

### Key Features

| Feature | Description |
|---------|-------------|
| **Dashboard** | Real-time KPI metrics (total NRs, aircraft count, aircraft types, operators) + 4 distribution charts |
| **Data Table** | Paginated browsing of the `aircraft_dummy` table |
| **AI Chat** | Natural language conversation with a Gemini 2.5 Flash agent — auto SQL generation and result analysis |
| **Inline Charts** | Automatic Bar / Doughnut / Line chart rendering inside agent responses |
| **Suggested Questions** | 3 context-aware follow-up questions auto-generated after each response |
| **Equipment Analysis Mode** | Deep-dive analysis for specific equipment such as APU, landing gear, engines |

---

### Tech Stack

- **Frontend**: Vanilla HTML/CSS/JS + Chart.js v4
- **Backend**: Python 3.11 / FastAPI / Uvicorn
- **AI Agent**: Google ADK (≥1.23) + Gemini 2.5 Flash
- **Database**: Google BigQuery (`cloud-cycle-pj.mdas-dataset.aircraft_dummy`)
- **Cloud**: Google Cloud Platform (Vertex AI)

---

### Project Structure

```
aircraft/
├── app.py                  # FastAPI entry point — router & dependency wiring only (25 lines)
├── config.py               # Single source of truth for env vars (Settings dataclass)
├── adk_runner.py           # Standalone CLI agent runner
│
├── db/                     # Data access layer — swap DB by modifying only this layer
│   ├── base.py             # DataStore ABC (interface definition)
│   ├── bigquery.py         # BigQuery implementation
│   └── __init__.py         # create_datastore() factory (branched by DB_TYPE env var)
│
├── api/                    # FastAPI routers
│   ├── chat.py             # POST /api/chat — ADK session management
│   └── data.py             # GET  /api/data/* — summary / charts / table / search
│
├── agent/                  # ADK agent
│   ├── prompt.py           # System prompt factory (build_system_prompt)
│   ├── agent.py            # Agent builder — config-injected, no hardcoding
│   └── __init__.py
│
├── static/
│   ├── index.html          # SPA frontend
│   └── chart.min.js        # Chart.js bundle
│
├── Dockerfile              # Container image for Cloud Run
├── cloudbuild.yaml         # CI/CD — build → push to Artifact Registry → deploy to Cloud Run
├── terraform/              # IaC — full GCP infrastructure definition
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── apis.tf
│   ├── iam.tf
│   ├── artifact_registry.tf
│   ├── bigquery.tf
│   ├── cloud_run.tf
│   ├── iap.tf
│   └── terraform.tfvars.example
├── requirements.txt
├── .env.example
├── ARCHITECTURE.md
└── README.md
```

#### Plugging in a Different DB Backend

Add a file implementing the `DataStore` ABC under `db/`, add one branch line in `db/__init__.py`, and set `DB_TYPE` in `.env`.

```
# Example: adding a PostgreSQL backend
db/postgres.py          ← DataStore subclass implementation
db/__init__.py          ← add "postgres" branch (1 line)
.env                    ← DB_TYPE=postgres
```

---

### Quick Start

#### 1. Configure Environment Variables

```bash
cp .env.example .env
```

Open `.env` and fill in your GCP project details:

```dotenv
GOOGLE_CLOUD_PROJECT=cloud-cycle-pj
BIGQUERY_DATASET=mdas-dataset
BIGQUERY_TABLE=aircraft_dummy
BIGQUERY_REGION=asia-southeast3
GOOGLE_CLOUD_LOCATION=asia-southeast1
GOOGLE_GENAI_USE_VERTEXAI=true

# Data backend selection (default: bigquery)
DB_TYPE=bigquery
```

#### 2. GCP Authentication

```bash
gcloud auth application-default login
```

Or with a service account key:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

#### 3. Run the Server

**Virtual environment setup (first time only)**

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**Start server (dev mode — hot reload)**

```bash
make dev
# or directly:
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

**Run with Docker**

```bash
make run
```

Open `http://localhost:8080` in your browser to view the dashboard.

#### 4. CLI Mode (optional)

Chat with the agent directly in the terminal without starting the web server:

```bash
source venv/bin/activate
python adk_runner.py
```

```
=== Aircraft Intelligence Agent ===
Type your question (or 'quit' to exit)

You: Show me the top 10 ATA codes by NR count
Agent: ...
```

---

### GCP Deployment (Terraform + Cloud Run)

#### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- Docker
- Owner or Editor permission on the GCP project

#### Resources Managed by Terraform

| File | Resources Created |
|------|-------------------|
| `apis.tf` | Enables Cloud Run, BigQuery, Artifact Registry, Cloud Build, IAP, Compute APIs |
| `iam.tf` | Service account + BigQuery & Cloud Run IAM bindings |
| `artifact_registry.tf` | Docker image repository |
| `bigquery.tf` | `mdas-dataset` dataset + `aircraft_dummy` table schema |
| `cloud_run.tf` | Cloud Run v2 service (LB-only ingress, scaling, health checks, env vars) |
| `iap.tf` | Global HTTPS LB + Serverless NEG + IAP OAuth client + SSL certificate |

#### Deployment Steps

**Step 1 — Set variables**

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
project_id          = "your-gcp-project-id"
region              = "us-central1"
iap_support_email   = "admin@your-org.com"
iap_allowed_members = ["user:admin@your-org.com"]
# domain = "dashboard.example.com"  # omit if no custom domain (nip.io auto-used)
```

**Step 2 — Create Artifact Registry first**

```bash
terraform init
terraform apply -target=google_artifact_registry_repository.docker
```

**Step 3 — Build & push Docker image**

```bash
cd ..
gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/aircraft-dashboard-images/aircraft-dashboard:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/aircraft-dashboard-images/aircraft-dashboard:latest
```

**Step 4 — Create LB static IP first (for nip.io domain calculation)**

```bash
cd terraform
terraform apply -target=google_compute_global_address.lb_ip
```

**Step 5 — Deploy full infrastructure**

```bash
terraform apply
```

**Step 6 — Get access URL**

```bash
terraform output iap_url       # IAP-protected URL (for actual access)
terraform output lb_ip_address # LB IP for DNS registration
```

> **SSL certificate**: After first deployment, certificate provisioning takes 10–30 minutes.  
> Check `ACTIVE` status with `gcloud compute ssl-certificates describe aircraft-dashboard-cert --global` before accessing.

> **Existing IAP brand**: If the project already has an IAP brand, import it:  
> `terraform import google_iap_brand.project_brand projects/PROJECT_NUMBER/brands/PROJECT_NUMBER`

#### CI/CD (Cloud Build)

Connect `cloudbuild.yaml` to a Cloud Build trigger to auto-build and deploy on every code push:

```
Code Push
  → Cloud Build trigger
  → Docker image build
  → Push to Artifact Registry (COMMIT_SHA + latest tags)
  → Auto-deploy to Cloud Run
```

---

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | SPA entry point |
| `POST` | `/api/chat` | AI agent conversation |
| `GET` | `/api/data/summary` | KPI aggregation (total NRs, aircraft count, etc.) |
| `GET` | `/api/data/charts` | Top-10 distribution data for charts |
| `GET` | `/api/data/table` | Paginated table (`?limit=50&offset=0`) |
| `GET` | `/api/data/search` | Full-text search (`?q=keyword`) |

---

### AI Agent Analysis Examples

**General Analysis**
- "Show the distribution of aircraft types as a pie chart"
- "Top 10 ATA codes by NR count"
- "Monthly NR occurrence trend analysis"

**Equipment Deep Dive**
- "Analyze APU-related NR records and show defect patterns by aircraft type"
- "Show the full NR status and monthly trend for ATA 32 (landing gear)"
- "Find aircraft registration numbers with the highest repeat NR occurrence for engine-related issues"

---

### Architecture

See [ARCHITECTURE.md](./ARCHITECTURE.md) for detailed diagrams and data flow.

Key flow:

```
User (Browser)
  → Global HTTPS LB
  → IAP (Google account auth — only allowed users pass)
  → Serverless NEG
  → Cloud Run (LB-only ingress)
  → app.py (FastAPI — router wiring)
       ├─ api/data.py  ──→ db/DataStore (BigQuery / other backends)
       │                        ↓
       │                   summary / charts / table / search
       │
       └─ api/chat.py  ──→ ADK Runner
                                ↓
                          agent/agent.py  (Gemini 2.5 Flash)
                                ↓
                          BigQueryToolset / CAA Toolset
                                ↓
                           BigQuery
                                ↓
              Response + CHART_DATA + SEARCH_DATA + SUGGESTED_QUESTIONS
                                ↓
              api/chat.py parsing → frontend rendering
```

#### Access Security

| Component | Role |
|-----------|------|
| **IAP (Identity-Aware Proxy)** | Google account auth — only users in `iap_allowed_members` can access |
| **Global HTTPS LB** | SSL termination + HTTP→HTTPS redirect |
| **Cloud Run ingress restriction** | `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` — blocks direct access bypassing LB |
| **nip.io SSL** | Google-managed SSL certificate auto-provisioned without a custom domain |

---

### Dependencies

```
google-adk>=1.23.0
google-cloud-bigquery>=3.11.0
google-auth>=2.22.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-dotenv>=1.0.0
google-cloud-aiplatform>=1.38.0
pydantic>=2.4.0
```

---

### BigQuery Table Schema

`cloud-cycle-pj.mdas-dataset.aircraft_dummy`

| Column | Description |
|--------|-------------|
| `ID` | Record identifier |
| `NR_NUMBER` | Non-routine work order number |
| `MALFUNCTION` | Defect description |
| `CORRECTIVE_ACTION` | Corrective action taken |
| `NR_REQUEST_DATE` | NR occurrence date |
| `AC_TYPE` | Aircraft type (e.g. B737, A320) |
| `AC_NO` | Aircraft registration number |
| `MSG_NO` | Message number |
| `AMP` | Operator / maintenance program |
| `COMPONENT_KEYWORD` | Component keywords (comma-separated, e.g. "ENGINE,APU") |
| `ATA_CODE` | ATA chapter code |
| `NR_WORKORDER_NAME` | Work order name |

---

<a name="한국어"></a>
## 한국어

항공기 비정형 정비(NR) 기록을 AI로 분석하는 웹 대시보드입니다.  
Google ADK + Gemini 2.5 Flash + BigQuery를 기반으로 자연어 질문으로 정비 데이터를 조회하고 시각화합니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **대시보드** | KPI 지표(총 NR 수, 항공기 수, 기종 수, 운항사 수) + 4개 분포 차트 실시간 조회 |
| **데이터 테이블** | `aircraft_dummy` 테이블 페이지네이션 브라우징 |
| **AI 채팅** | Gemini 2.5 Flash 에이전트와 자연어 대화 — SQL 자동 생성 및 결과 분석 |
| **인라인 차트** | 에이전트 응답에 Bar / Doughnut / Line 차트 자동 렌더링 |
| **추천 질문** | 매 응답 후 맥락 기반 후속 질문 3개 자동 제안 |
| **설비 분석 모드** | APU, 랜딩기어, 엔진 등 특정 설비를 지정해 심층 분석 |

---

## 기술 스택

- **Frontend**: Vanilla HTML/CSS/JS + Chart.js v4
- **Backend**: Python 3.11 / FastAPI / Uvicorn
- **AI Agent**: Google ADK (≥1.23) + Gemini 2.5 Flash
- **Database**: Google BigQuery (`cloud-cycle-pj.mdas-dataset.aircraft_dummy`)
- **Cloud**: Google Cloud Platform (Vertex AI)

---

## 프로젝트 구조

```
aircraft/
├── app.py                  # FastAPI 진입점 — 라우터·의존성 와이어링만 담당 (25줄)
├── config.py               # 환경변수 단일 진실 원천 (Settings dataclass)
├── adk_runner.py           # CLI용 standalone 에이전트 실행기
│
├── db/                     # 데이터 접근 레이어 — DB 교체 시 이 레이어만 수정
│   ├── base.py             # DataStore ABC (인터페이스 정의)
│   ├── bigquery.py         # BigQuery 구현체
│   └── __init__.py         # create_datastore() 팩토리 (DB_TYPE env로 분기)
│
├── api/                    # FastAPI 라우터
│   ├── chat.py             # POST /api/chat — ADK 세션 관리
│   └── data.py             # GET  /api/data/* — summary / charts / table / search
│
├── agent/                  # ADK 에이전트
│   ├── prompt.py           # 시스템 프롬프트 팩토리 (build_system_prompt)
│   ├── agent.py            # Agent 빌더 — config 주입, 하드코딩 없음
│   └── __init__.py
│
├── static/
│   ├── index.html          # SPA 프론트엔드
│   └── chart.min.js        # Chart.js 번들
│
├── Dockerfile              # Cloud Run용 컨테이너 이미지 정의
├── cloudbuild.yaml         # CI/CD — 빌드 → Artifact Registry 푸시 → Cloud Run 배포
├── terraform/              # IaC — GCP 인프라 전체 정의
│   ├── main.tf             # Provider 설정
│   ├── variables.tf        # 변수 정의
│   ├── outputs.tf          # 출력값 (URL, 이미지 URI 등)
│   ├── apis.tf             # GCP API 활성화
│   ├── iam.tf              # 서비스 계정 + IAM 바인딩
│   ├── artifact_registry.tf# Docker 이미지 저장소
│   ├── bigquery.tf         # 데이터셋 + 테이블 스키마
│   ├── cloud_run.tf        # Cloud Run v2 서비스 (ingress: LB 전용)
│   ├── iap.tf              # Global HTTPS LB + IAP + Serverless NEG + SSL
│   └── terraform.tfvars.example
├── requirements.txt        # Python 의존성
├── .env.example            # 환경변수 템플릿
├── ARCHITECTURE.md         # 아키텍처 상세 문서 + 다이어그램
└── README.md
```

### 다른 DB 백엔드 연결 방법

`DataStore` ABC를 구현하는 파일을 `db/` 에 추가하고, `db/__init__.py` 의 팩토리에 분기를 한 줄 추가한 뒤 `.env` 에서 `DB_TYPE` 을 지정하면 됩니다.

```
# 예: PostgreSQL 백엔드 추가
db/postgres.py          ← DataStore 서브클래스 구현
db/__init__.py          ← "postgres" 분기 추가 (1줄)
.env                    ← DB_TYPE=postgres
```

---

## 빠른 시작

### 1. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 GCP 프로젝트 정보를 확인합니다.

```dotenv
GOOGLE_CLOUD_PROJECT=cloud-cycle-pj
BIGQUERY_DATASET=mdas-dataset
BIGQUERY_TABLE=aircraft_dummy
BIGQUERY_REGION=asia-southeast3
GOOGLE_CLOUD_LOCATION=asia-southeast1
GOOGLE_GENAI_USE_VERTEXAI=true

# 데이터 백엔드 선택 (기본값: bigquery)
# 다른 DB를 추가한 경우 db/__init__.py 의 팩토리에 맞게 값을 변경
DB_TYPE=bigquery
```

### 2. GCP 인증

```bash
gcloud auth application-default login
```

또는 서비스 계정 키를 사용하는 경우:

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
```

### 3. 서버 실행

**가상환경 세팅 (최초 1회)**

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**서버 시작 (개발 모드 — 핫 리로드)**

```bash
make dev
# 또는 직접 실행:
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

**Docker로 실행**

```bash
make run
```

브라우저에서 `http://localhost:8080`을 열면 대시보드가 표시됩니다.

### 4. CLI 모드 (선택)

웹 서버 없이 터미널에서 에이전트와 직접 대화할 수 있습니다.

```bash
source venv/bin/activate
python adk_runner.py
```

```
=== Aircraft Intelligence Agent ===
Type your question (or 'quit' to exit)

You: ATA 코드별 NR 건수 상위 10개를 보여줘
Agent: ...
```

---

---

## GCP 배포 (Terraform + Cloud Run)

### 사전 요구사항

- [Terraform](https://developer.hashicorp.com/terraform/install) >= 1.5
- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud`)
- Docker
- GCP 프로젝트에 대한 Owner 또는 Editor 권한

### Terraform 관리 리소스

| 파일 | 생성되는 리소스 |
|------|----------------|
| `apis.tf` | Cloud Run, BigQuery, Artifact Registry, Cloud Build, IAP, Compute API 활성화 |
| `iam.tf` | 서비스 계정 + BigQuery·Cloud Run IAM 바인딩 |
| `artifact_registry.tf` | Docker 이미지 저장소 |
| `bigquery.tf` | `mdas-dataset` 데이터셋 + `aircraft_dummy` 테이블 스키마 |
| `cloud_run.tf` | Cloud Run v2 서비스 (ingress: LB 전용, 스케일링, 헬스체크, 환경변수) |
| `iap.tf` | Global HTTPS LB + Serverless NEG + IAP OAuth 클라이언트 + SSL 인증서 |

### 배포 순서

#### 1단계 — 변수 설정

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```

`terraform.tfvars`에서 필수 값을 설정합니다.

```hcl
project_id          = "your-gcp-project-id"
region              = "us-central1"
iap_support_email   = "admin@your-org.com"
iap_allowed_members = ["user:admin@your-org.com"]
# domain = "dashboard.example.com"  # 커스텀 도메인이 없으면 생략 (nip.io 자동 사용)
```

#### 2단계 — Artifact Registry 먼저 생성

```bash
terraform init
terraform apply -target=google_artifact_registry_repository.docker
```

#### 3단계 — Docker 이미지 빌드 & 푸시

```bash
cd ..   # 프로젝트 루트로 이동

gcloud auth configure-docker us-central1-docker.pkg.dev
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/aircraft-dashboard-images/aircraft-dashboard:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/aircraft-dashboard-images/aircraft-dashboard:latest
```

#### 4단계 — LB 정적 IP 먼저 생성 (nip.io 도메인 계산용)

```bash
cd terraform
terraform apply -target=google_compute_global_address.lb_ip
```

#### 5단계 — 전체 인프라 배포

```bash
terraform apply
```

#### 6단계 — 접속 URL 확인

```bash
terraform output iap_url       # IAP 보호 URL (실제 접속용)
terraform output lb_ip_address # DNS 등록용 LB IP
```

> **SSL 인증서**: 처음 배포 후 인증서 프로비저닝에 10~30분 소요됩니다.  
> `gcloud compute ssl-certificates describe aircraft-dashboard-cert --global` 에서 `ACTIVE` 상태 확인 후 접속하세요.

> **기존 IAP 브랜드**: 프로젝트에 IAP 브랜드가 이미 있는 경우 import가 필요합니다.  
> `terraform import google_iap_brand.project_brand projects/PROJECT_NUMBER/brands/PROJECT_NUMBER`

### CI/CD (Cloud Build)

`cloudbuild.yaml`을 Cloud Build 트리거에 연결하면 코드 Push 시 자동으로 빌드 → 배포됩니다.

```
코드 Push
  → Cloud Build 트리거
  → Docker 이미지 빌드
  → Artifact Registry 푸시 (COMMIT_SHA + latest 태그)
  → Cloud Run 자동 배포
```

> Cloud Run 이미지 버전은 `lifecycle.ignore_changes`로 Terraform 관리 범위에서 제외되므로, 배포 후 이미지 업데이트는 CI/CD가 담당합니다.

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| `GET` | `/` | SPA 진입점 |
| `POST` | `/api/chat` | AI 에이전트 대화 |
| `GET` | `/api/data/summary` | KPI 집계 (총 NR, 항공기 수 등) |
| `GET` | `/api/data/charts` | 차트용 Top-10 분포 데이터 |
| `GET` | `/api/data/table` | 페이지네이션 테이블 (`?limit=50&offset=0`) |
| `GET` | `/api/data/search` | 전체 텍스트 검색 (`?q=keyword`) |

---

## AI 에이전트 분석 예시

**일반 분석**
- "항공기 유형별 분포를 파이 차트로 보여줘"
- "NR 건수 기준 상위 10개 ATA 코드"
- "월별 NR 발생 추이 분석"

**설비 심층 분석**
- "APU 관련 NR 기록을 분석해서 결함 패턴과 주요 발생 기종을 알려줘"
- "ATA 32(랜딩기어) 시스템의 전체 NR 현황과 월별 추이를 보여줘"
- "엔진 관련 NR에서 반복 발생 빈도가 높은 항공기 등록번호를 찾아줘"

---

## 아키텍처

상세 아키텍처 다이어그램 및 데이터 흐름은 [ARCHITECTURE.md](./ARCHITECTURE.md)를 참조하세요.

주요 흐름:

```
사용자 (브라우저)
  → Global HTTPS LB
  → IAP (Google 계정 인증 — 허용된 사용자만 통과)
  → Serverless NEG
  → Cloud Run (ingress: LB 전용)
  → app.py (FastAPI — 라우터 와이어링)
       ├─ api/data.py  ──→ db/DataStore (BigQuery / 기타 백엔드)
       │                        ↓
       │                   summary / charts / table / search
       │
       └─ api/chat.py  ──→ ADK Runner
                                ↓
                          agent/agent.py  (Gemini 2.5 Flash)
                                ↓
                          BigQueryToolset / CAA Toolset
                                ↓
                           BigQuery
                                ↓
              응답 + CHART_DATA + SEARCH_DATA + SUGGESTED_QUESTIONS
                                ↓
              api/chat.py 파싱 → 프론트엔드 렌더링
```

### 접근 보안

| 구성 요소 | 역할 |
|-----------|------|
| **IAP (Identity-Aware Proxy)** | Google 계정 인증 — `iap_allowed_members`에 등록된 사용자만 접근 허용 |
| **Global HTTPS LB** | SSL 종료 + HTTP→HTTPS 리다이렉트 |
| **Cloud Run ingress 제한** | `INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER` — LB 외 직접 접근 차단 |
| **nip.io SSL** | 커스텀 도메인 없이 Google 관리 SSL 인증서 자동 발급 |

---

## 의존성

```
google-adk>=1.23.0
google-cloud-bigquery>=3.11.0
google-auth>=2.22.0
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-dotenv>=1.0.0
google-cloud-aiplatform>=1.38.0
pydantic>=2.4.0
```

---

## BigQuery 테이블 스키마

`cloud-cycle-pj.mdas-dataset.aircraft_dummy`

| 컬럼 | 설명 |
|------|------|
| `ID` | 레코드 식별자 |
| `NR_NUMBER` | 비정형 작업 지시 번호 |
| `MALFUNCTION` | 결함 설명 |
| `CORRECTIVE_ACTION` | 교정 조치 내용 |
| `NR_REQUEST_DATE` | NR 발생일 |
| `AC_TYPE` | 항공기 기종 (예: B737, A320) |
| `AC_NO` | 항공기 등록번호 |
| `MSG_NO` | 메시지 번호 |
| `AMP` | 운항사 / 정비 프로그램 |
| `COMPONENT_KEYWORD` | 컴포넌트 키워드 (콤마 구분, 예: "ENGINE,APU") |
| `ATA_CODE` | ATA 챕터 코드 |
| `NR_WORKORDER_NAME` | 작업 지시 명칭 |
