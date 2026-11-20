# API

Base URL: `http://127.0.0.1:8000`

## Health

- `GET /api/health`

## Projects

- `POST /api/v1/projects`
- `GET /api/v1/projects`
- `GET /api/v1/projects/{id}`

## Models

- `POST /api/v1/models/import`
- `GET /api/v1/projects/{project_id}/models`
- `GET /api/v1/models/{id}`
- `GET /api/v1/models/{id}/file`
- `POST /api/v1/models/{id}/process`
- `POST /api/v1/models/{id}/validate`
- `POST /api/v1/models/{id}/export`（需要 `confirmed=true`）
- `GET /api/v1/models/{id}/files`

## Generation

- `POST /api/v1/generation`
- `POST /api/v1/generation/image-to-3d`
- `GET /api/v1/generation/{id}`
- `POST /api/v1/generation/{id}/download`

## Print jobs

- `POST /api/v1/print-jobs`
- `GET /api/v1/print-jobs`
- `PATCH /api/v1/print-jobs/{id}`
- `POST /api/v1/print-jobs/{id}/open-slicer`
