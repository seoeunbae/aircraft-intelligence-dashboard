# 앱 전용 서비스 계정
resource "google_service_account" "app" {
  account_id   = "${var.service_name}-sa"
  display_name = "Aircraft Dashboard Service Account"
  description  = "Cloud Run 서비스 계정 — BigQuery 조회 및 Vertex AI 접근"
  project      = var.project_id

  depends_on = [google_project_service.apis]
}

# BigQuery 데이터 읽기
resource "google_project_iam_member" "bq_data_viewer" {
  project = var.project_id
  role    = "roles/bigquery.dataViewer"
  member  = "serviceAccount:${google_service_account.app.email}"
}

# BigQuery 쿼리 실행
resource "google_project_iam_member" "bq_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.app.email}"
}

# Cloud Run 서비스 공개 접근 (allow_public_access=true 일 때만)
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  count = var.allow_public_access ? 1 : 0

  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# Cloud Build 서비스 계정이 Cloud Run 배포 가능하도록
resource "google_project_iam_member" "cloudbuild_run_admin" {
  project = var.project_id
  role    = "roles/run.admin"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "cloudbuild_sa_user" {
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
  member  = "serviceAccount:${data.google_project.project.number}@cloudbuild.gserviceaccount.com"

  depends_on = [google_project_service.apis]
}

data "google_project" "project" {
  project_id = var.project_id
}
