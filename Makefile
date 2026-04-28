PROJECT_ID   := cloud-cycle-pj
REGION       := us-central1
SERVICE      := aircraft-dashboard
REPO         := aircraft-dashboard-images
IMAGE        := $(REGION)-docker.pkg.dev/$(PROJECT_ID)/$(REPO)/$(SERVICE)
TAG          ?= latest
PORT         ?= 8080

.PHONY: help build push deploy run dev logs describe cloudbuild tf-init tf-plan tf-apply tf-destroy

help:
	@echo "Aircraft Dashboard — available commands:"
	@echo ""
	@echo "  Local development:"
	@echo "    make dev          Run app locally with uvicorn (hot-reload)"
	@echo "    make run          Run app locally in Docker"
	@echo "    make build        Build Docker image locally"
	@echo ""
	@echo "  GCP deployment:"
	@echo "    make push         Push image to Artifact Registry"
	@echo "    make deploy       Deploy image to Cloud Run (us-central1)"
	@echo "    make cloudbuild   Submit full build+push+deploy via Cloud Build"
	@echo ""
	@echo "  Observability:"
	@echo "    make logs         Stream Cloud Run logs"
	@echo "    make describe     Show Cloud Run service details"
	@echo "    make url          Print the service URL"
	@echo ""
	@echo "  Terraform:"
	@echo "    make tf-init      terraform init"
	@echo "    make tf-plan      terraform plan"
	@echo "    make tf-apply     terraform apply"
	@echo "    make tf-destroy   terraform destroy"
	@echo ""
	@echo "  Variables (override with make VAR=value):"
	@echo "    TAG=$(TAG)   IMAGE=$(IMAGE)"

# ── Local ──────────────────────────────────────────────────────────────────────

dev:
	uvicorn app:app --host 0.0.0.0 --port $(PORT) --reload

build:
	docker build -t $(IMAGE):$(TAG) .

run: build
	docker run --rm -p $(PORT):8080 --env-file .env $(IMAGE):$(TAG)

# ── GCP Deployment ─────────────────────────────────────────────────────────────

push: build
	docker push $(IMAGE):$(TAG)

deploy:
	gcloud run deploy $(SERVICE) \
		--image $(IMAGE):$(TAG) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--platform managed \
		--quiet

cloudbuild:
	gcloud builds submit \
		--config deploy/cloudbuild.yaml \
		--project $(PROJECT_ID) \
		--region $(REGION) \
		--substitutions=COMMIT_SHA=$(shell git rev-parse --short HEAD) \
		.

# ── Observability ──────────────────────────────────────────────────────────────

logs:
	gcloud run services logs tail $(SERVICE) \
		--region $(REGION) \
		--project $(PROJECT_ID)

describe:
	gcloud run services describe $(SERVICE) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--format yaml

url:
	@gcloud run services describe $(SERVICE) \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--format "value(status.url)"

# ── Terraform ──────────────────────────────────────────────────────────────────

tf-init:
	terraform -chdir=terraform init

tf-plan:
	terraform -chdir=terraform plan

tf-apply:
	terraform -chdir=terraform apply

tf-destroy:
	terraform -chdir=terraform destroy
