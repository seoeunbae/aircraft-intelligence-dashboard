# GOOGLE_API_KEY를 Secret Manager에 저장하고 Cloud Run에서 참조
resource "google_secret_manager_secret" "api_key" {
  project   = var.project_id
  secret_id = "${var.service_name}-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

# 실제 API Key 값은 terraform apply 후 별도로 설정:
#   gcloud secrets versions add aircraft-dashboard-api-key --data-file=<(echo -n "YOUR_API_KEY")
# 또는 아래 resource를 사용해 직접 주입 (민감 정보 주의)
resource "google_secret_manager_secret_version" "api_key_value" {
  secret      = google_secret_manager_secret.api_key.id
  secret_data = var.google_api_key
}

# Cloud Run 서비스 계정에 Secret 읽기 권한
resource "google_secret_manager_secret_iam_member" "app_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.app.email}"
}
