# Phase 6 Ingestion Implementation Plan

> **For agentic workers:** Implement task-by-task; adapters keep demo + Compose on one pipeline.

**Goal:** Import Confluence Sources end-to-end (Direct + Agent), store pages/attachments (images + draw.io), chunk/embed, UI import + draw.io viewer; works on demo and Compose.

**Architecture:** Unified ingest pipeline with Storage (MinIO|local), Queue (Celery|inline), Embedding HTTP stub. Agent jobs FETCH_CONFLUENCE + payload upload feed same normalize/index path.

**Tech Stack:** FastAPI, Celery/Redis, boto3/MinIO, BeautifulSoup sanitize, embedding-service, Next.js viewer

## Tasks

- [x] Spec
- [x] Models + Alembic 0006
- [x] Storage + queue + embed clients
- [x] Ingest service (Direct) + agent fetch/upload
- [x] APIs + worker task
- [x] UI import + documents + draw.io viewer
- [x] Tests + docs
