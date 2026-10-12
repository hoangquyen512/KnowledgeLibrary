# Thuật ngữ QA — Knowledge Library

| Thuật ngữ | Ý nghĩa |
|-----------|---------|
| Workspace | Ranh giới tenant; mọi dữ liệu AI/search gắn workspace |
| Space | Không gian tri thức trong workspace |
| Source | Nguồn ingest: Confluence, Jira, file upload |
| RBAC | OWNER / EDITOR / VIEWER (workspace & space) |
| Isolated share | Share space — viewer không list workspace |
| Ingestion job | Pipeline SCAN→…→EMBED cho import/sync |
| Citation | Trích dẫn chunk trong câu trả lời Ask AI |
| Super Admin | Vai trò platform; không duyệt nội dung tài liệu |

**Prefix dữ liệu test:** `QA-{module}-{uuid6}` — dọn định kỳ trên DB dev/staging.
