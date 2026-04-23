variable "project_id" {
  description = "GCP 프로젝트 ID"
  type        = string
}

variable "region" {
  description = "Cloud Run 및 Artifact Registry 리전"
  type        = string
  default     = "asia-southeast1"
}

variable "bigquery_region" {
  description = "BigQuery 데이터셋 위치"
  type        = string
  default     = "asia-southeast3"
}

variable "bigquery_dataset" {
  description = "BigQuery 데이터셋 ID"
  type        = string
  default     = "mdas-dataset"
}

variable "bigquery_table" {
  description = "BigQuery 테이블 ID"
  type        = string
  default     = "aircraft_dummy"
}

variable "service_name" {
  description = "Cloud Run 서비스 이름"
  type        = string
  default     = "aircraft-dashboard"
}

variable "image_tag" {
  description = "배포할 Docker 이미지 태그 (초기 배포 후 CI/CD가 관리)"
  type        = string
  default     = "latest"
}

variable "cloud_run_min_instances" {
  description = "Cloud Run 최소 인스턴스 수 (0 = cold start 허용)"
  type        = number
  default     = 0
}

variable "cloud_run_max_instances" {
  description = "Cloud Run 최대 인스턴스 수"
  type        = number
  default     = 3
}

variable "cloud_run_cpu" {
  description = "Cloud Run 컨테이너 CPU 한도"
  type        = string
  default     = "2"
}

variable "cloud_run_memory" {
  description = "Cloud Run 컨테이너 메모리 한도"
  type        = string
  default     = "2Gi"
}

variable "allow_public_access" {
  description = "Cloud Run 서비스에 인증 없이 접근 허용 여부"
  type        = bool
  default     = true
}

variable "google_api_key" {
  description = "Google Generative AI API Key (GOOGLE_GENAI_USE_VERTEXAI=false 일 때 사용)"
  type        = string
  sensitive   = true
}

variable "domain" {
  description = "커스텀 도메인 (없으면 null — LB IP 기반 nip.io 도메인 자동 사용)"
  type        = string
  default     = null
}

variable "iap_support_email" {
  description = "IAP OAuth 동의 화면에 표시될 지원 이메일 (사용자 또는 그룹 이메일)"
  type        = string
}

variable "iap_allowed_members" {
  description = "IAP를 통해 접근 허용할 사용자/그룹 목록 (예: [\"user:email@example.com\", \"group:team@example.com\"])"
  type        = list(string)
  default     = []
}
