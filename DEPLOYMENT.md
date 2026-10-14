# Deploy Production — Knowledge Library (Render)

Giống project [Novel](https://github.com/hoangquyen512/Novel): đẩy GitHub → Blueprint `render.yaml` → URL `*.onrender.com`.

| Môi trường | Cách chạy | URL |
|------------|-----------|-----|
| **Dev** | Docker Compose / local | http://localhost:3000 |
| **Prod (VPS)** | `docker-compose.prod.yml` | xem README |
| **Prod (Render free)** | Blueprint `render.yaml` | `https://kl-web.onrender.com` |

---

## Bạn đã có project Render trống

Ví dụ: https://dashboard.render.com/project/prj-db7iq2g473hc73di0e70

### Bước 1 — Code đã có `render.yaml` trên GitHub `main`

Repo: https://github.com/hoangquyen512/KnowledgeLibrary

Nếu chưa thấy file `render.yaml` trên `main`, pull/push lại rồi tiếp.

### Bước 2 — Tạo Blueprint trong project

1. Mở project trên Dashboard.
2. **New** → **Blueprint** (hoặc *Apply Blueprint*).
3. Connect repo **hoangquyen512/KnowledgeLibrary**, branch **main**.
4. Render đọc `render.yaml` → tạo:
   - Postgres `kl-db` (free, **hết hạn sau 30 ngày**)
   - Redis `kl-redis` (free)
   - Web `kl-embedding`, `kl-api`, `kl-web` (free)
5. Khi hỏi env `sync: false`, điền tạm hoặc bỏ trống rồi sửa sau:
   - `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` (cần để login Google)
   - `SEED_SUPER_ADMIN_EMAIL` (email Google của bạn)
   - `S3_*` — có thể để trống lần đầu (upload file chưa dùng được)

### Bước 3 — Chờ build

Free tier build có thể mất 10–20 phút. Xem Logs từng service.

### Bước 4 — Kiểm tra

- API: `https://kl-api.onrender.com/health` → `{"status":"ok",...}`
- Ready: `https://kl-api.onrender.com/ready` → database + redis `ok`
- Web: `https://kl-web.onrender.com`
- Embedding: `https://kl-embedding.onrender.com/health`

Lần mở đầu sau khi sleep (~15 phút không traffic) có thể chờ 30–60 giây (giống Novel).

### Bước 5 — Google OAuth

Trong Google Cloud Console → OAuth client, thêm Authorized redirect URI:

```
https://kl-api.onrender.com/api/v1/auth/google/callback
```

Trên Render → `kl-api` → Environment, điền `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SEED_SUPER_ADMIN_EMAIL` → **Manual Deploy**.

### Bước 6 — (Tuỳ chọn) Object storage

Upload/ingestion file cần S3-compatible (Cloudflare R2 free, AWS S3, MinIO…). Điền `S3_ENDPOINT`, `S3_PUBLIC_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_BUCKET` trên `kl-api`.

---

## Giới hạn gói Free (quan trọng)

- Web **ngủ** khi không ai truy cập.
- Postgres free **expire 30 ngày** (upgrade hoặc export trước khi mất).
- Không có Celery worker riêng → job ingestion chạy **inline** trong API (chậm hơn, đủ demo).
- Không có MinIO trong blueprint → cần S3 bên ngoài nếu upload file.
- Embedding là **stub** deterministic (chưa phải BGE-M3 thật).

---

## Deploy lại sau khi sửa code

Push lên `main` → Render auto-deploy các web service (nếu đã bật auto-deploy).
