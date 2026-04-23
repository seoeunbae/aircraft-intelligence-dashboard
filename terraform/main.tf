terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # GCS 백엔드 사용 시 아래 주석 해제
  # backend "gcs" {
  #   bucket = "your-terraform-state-bucket"
  #   prefix = "aircraft-dashboard/state"
  # }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
