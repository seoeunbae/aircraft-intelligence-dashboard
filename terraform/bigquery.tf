resource "google_bigquery_dataset" "main" {
  project       = var.project_id
  dataset_id    = var.bigquery_dataset
  friendly_name = "MDAS Dataset"
  description   = "Aircraft Maintenance Data Analysis System — 항공기 비정형 정비 기록"
  location      = var.bigquery_region

  depends_on = [google_project_service.apis]
}

# aircraft_dummy 테이블은 기존 데이터가 있어 Terraform 외부에서 관리됩니다.
# 스키마 참조는 ARCHITECTURE.md를 확인하세요.

# Cloud Run 서비스 계정에 데이터셋 수준 읽기 권한
resource "google_bigquery_dataset_iam_member" "app_viewer" {
  project    = var.project_id
  dataset_id = google_bigquery_dataset.main.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.app.email}"
}
