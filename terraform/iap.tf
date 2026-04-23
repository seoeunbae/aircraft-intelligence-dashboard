# ─── nip.io 자동 도메인 (커스텀 도메인이 없을 때 LB IP → <IP>.nip.io 자동 생성) ──
locals {
  domain = var.domain != null ? var.domain : "${replace(google_compute_global_address.lb_ip.address, ".", "-")}.nip.io"
}

# ─── IAP OAuth 브랜드 ──────────────────────────────────────────────────────────
# 프로젝트당 1개만 생성 가능하며 삭제 불가합니다.
# 이미 존재하면: terraform import google_iap_brand.project_brand projects/<PROJECT_ID>/brands/<BRAND_ID>
resource "google_iap_brand" "project_brand" {
  support_email     = var.iap_support_email
  application_title = "Aircraft Intelligence Dashboard"
  project           = data.google_project.project.number

  lifecycle {
    ignore_changes = [application_title, support_email]
  }

  depends_on = [google_project_service.apis]
}

# ─── IAP OAuth 클라이언트 ─────────────────────────────────────────────────────
resource "google_iap_client" "project_client" {
  display_name = "Aircraft Dashboard IAP Client"
  brand        = google_iap_brand.project_brand.name
}

# ─── 정적 글로벌 외부 IP ──────────────────────────────────────────────────────
resource "google_compute_global_address" "lb_ip" {
  name    = "${var.service_name}-lb-ip"
  project = var.project_id

  depends_on = [google_project_service.apis]
}

# ─── Google 관리 SSL 인증서 ───────────────────────────────────────────────────
resource "google_compute_managed_ssl_certificate" "lb_cert" {
  name    = "${var.service_name}-cert"
  project = var.project_id

  managed {
    domains = [local.domain]
  }

  lifecycle {
    create_before_destroy = true
  }

  depends_on = [google_project_service.apis]
}

# ─── Serverless NEG (Cloud Run 백엔드) ────────────────────────────────────────
resource "google_compute_region_network_endpoint_group" "cloud_run_neg" {
  name                  = "${var.service_name}-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region
  project               = var.project_id

  cloud_run {
    service = google_cloud_run_v2_service.app.name
  }

  depends_on = [google_project_service.apis]
}

# ─── 백엔드 서비스 (IAP 포함) ─────────────────────────────────────────────────
resource "google_compute_backend_service" "lb_backend" {
  name                  = "${var.service_name}-backend"
  project               = var.project_id
  load_balancing_scheme = "EXTERNAL_MANAGED"

  backend {
    group = google_compute_region_network_endpoint_group.cloud_run_neg.id
  }

  iap {
    oauth2_client_id     = google_iap_client.project_client.client_id
    oauth2_client_secret = google_iap_client.project_client.secret
  }
}

# ─── URL 맵 ───────────────────────────────────────────────────────────────────
resource "google_compute_url_map" "lb_url_map" {
  name            = "${var.service_name}-url-map"
  project         = var.project_id
  default_service = google_compute_backend_service.lb_backend.id
}

# ─── HTTPS 타겟 프록시 ────────────────────────────────────────────────────────
resource "google_compute_target_https_proxy" "lb_https_proxy" {
  name             = "${var.service_name}-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.lb_url_map.id
  ssl_certificates = [google_compute_managed_ssl_certificate.lb_cert.id]
}

# ─── HTTPS 전달 규칙 ──────────────────────────────────────────────────────────
resource "google_compute_global_forwarding_rule" "lb_https" {
  name                  = "${var.service_name}-https"
  project               = var.project_id
  target                = google_compute_target_https_proxy.lb_https_proxy.id
  port_range            = "443"
  ip_address            = google_compute_global_address.lb_ip.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# ─── HTTP → HTTPS 리다이렉트 ──────────────────────────────────────────────────
resource "google_compute_url_map" "http_redirect" {
  name    = "${var.service_name}-http-redirect"
  project = var.project_id

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "http_redirect" {
  name    = "${var.service_name}-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.http_redirect.id
}

resource "google_compute_global_forwarding_rule" "lb_http" {
  name                  = "${var.service_name}-http"
  project               = var.project_id
  target                = google_compute_target_http_proxy.http_redirect.id
  port_range            = "80"
  ip_address            = google_compute_global_address.lb_ip.address
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# ─── Cloud Run: IAP 서비스 계정에 invoker 권한 부여 ───────────────────────────
# allUsers는 조직 정책(DomainRestrictedSharing)으로 차단되므로 IAP SA 사용
resource "google_cloud_run_v2_service_iam_member" "iap_invoker" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.app.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:service-${data.google_project.project.number}@gcp-sa-iap.iam.gserviceaccount.com"
}

# ─── IAP 접근 허용 사용자/그룹 ────────────────────────────────────────────────
resource "google_iap_web_backend_service_iam_binding" "iap_access" {
  project             = var.project_id
  web_backend_service = google_compute_backend_service.lb_backend.name
  role                = "roles/iap.httpsResourceAccessor"
  members             = var.iap_allowed_members
}
