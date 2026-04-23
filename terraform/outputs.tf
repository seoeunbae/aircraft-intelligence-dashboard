output "cloud_run_url" {
  description = "배포된 Aircraft Dashboard URL"
  value       = google_cloud_run_v2_service.app.uri
}

output "service_account_email" {
  description = "Cloud Run 서비스 계정 이메일"
  value       = google_service_account.app.email
}

output "artifact_registry_repo" {
  description = "Docker 이미지 저장소 경로"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}"
}

output "docker_image_uri" {
  description = "배포된 Docker 이미지 전체 URI"
  value       = local.image_uri
}

output "bigquery_table_fqn" {
  description = "BigQuery 테이블 완전 경로"
  value       = "${var.project_id}.${var.bigquery_dataset}.${var.bigquery_table}"
}

output "lb_ip_address" {
  description = "Load Balancer 정적 IP (DNS A 레코드에 이 값으로 등록 필요)"
  value       = google_compute_global_address.lb_ip.address
}

output "iap_url" {
  description = "IAP로 보호된 애플리케이션 접속 URL"
  value       = "https://${local.domain}"
}

output "docker_push_command" {
  description = "이미지 빌드 및 푸시 명령어"
  value       = <<-EOT
    # 1) Docker 인증
    gcloud auth configure-docker ${var.region}-docker.pkg.dev

    # 2) 이미지 빌드 & 푸시
    docker build -t ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}/${var.service_name}:latest .
    docker push ${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}/${var.service_name}:latest

    # 3) Cloud Run 배포
    gcloud run deploy ${var.service_name} \
      --image=${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.docker.repository_id}/${var.service_name}:latest \
      --region=${var.region}
  EOT
}
