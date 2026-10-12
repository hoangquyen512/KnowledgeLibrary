# Entity Relationship Diagram

Mermaid ERD for MVP core entities. Soft-delete and audit fields abbreviated where repeated.

```mermaid
erDiagram
  users ||--o| user_settings : has
  users ||--o{ ai_credentials : owns
  users ||--o{ workspace_memberships : member_of
  users ||--o{ space_memberships : member_of
  users ||--o{ conversations : owns
  users ||--o{ audit_logs : acts
  users ||--o{ ai_usage : incurs

  workspaces ||--o{ workspace_memberships : has
  workspaces ||--o{ spaces : contains
  workspaces ||--o{ share_links : shares
  workspaces ||--o{ confluence_connections : connects
  workspaces ||--o{ connector_agents : registers
  workspaces ||--o{ conversations : scopes
  workspaces ||--o{ audit_logs : scoped

  spaces ||--o{ space_memberships : has
  spaces ||--o{ sources : contains
  spaces ||--o{ share_links : shares
  spaces ||--o{ conversation_spaces : selected_in

  confluence_connections ||--o{ sources : used_by
  connector_agents ||--o{ confluence_connections : may_serve
  connector_agents ||--o{ ingestion_jobs : executes

  sources ||--o{ documents : has
  sources ||--o{ attachments : has
  sources ||--o{ ingestion_jobs : runs
  sources ||--o{ document_chunks : indexes

  documents ||--o{ documents : parent_of
  documents ||--o{ attachments : has
  documents ||--o{ document_chunks : chunked_into
  documents ||--o{ document_versions : versions
  documents ||--o{ citations : cited_as

  ingestion_jobs ||--o{ ingestion_job_errors : reports

  share_links ||--o{ share_link_redemptions : redeemed_by

  conversations ||--o{ conversation_spaces : selects
  conversations ||--o{ messages : contains
  messages ||--o{ message_space_scope : scoped
  messages ||--o{ citations : cites
  document_chunks ||--o{ citations : evidence

  users {
    uuid id PK
    string google_sub UK
    string email UK
    bool email_verified
    string display_name
    string avatar_url
    string status
    bool is_super_admin
    timestamptz last_login_at
    timestamptz created_at
    timestamptz updated_at
  }

  user_settings {
    uuid id PK
    uuid user_id FK
    string locale
    string theme
    string default_model
  }

  ai_credentials {
    uuid id PK
    uuid user_id FK
    string provider
    string credential_type
    bytes encrypted_secret
    string masked_suffix
    string status
    timestamptz last_validated_at
    string last_error
  }

  workspaces {
    uuid id PK
    string name
    string slug
    string description
    uuid created_by_user_id FK
    string status
    timestamptz deleted_at
  }

  workspace_memberships {
    uuid id PK
    uuid workspace_id FK
    uuid user_id FK
    string role
    string source
    uuid granted_by_user_id FK
    timestamptz revoked_at
  }

  spaces {
    uuid id PK
    uuid workspace_id FK
    string name
    string slug
    string description
    uuid created_by_user_id FK
    string status
    timestamptz deleted_at
  }

  space_memberships {
    uuid id PK
    uuid space_id FK
    uuid user_id FK
    string role
    string source
    uuid granted_by_user_id FK
    timestamptz revoked_at
  }

  share_links {
    uuid id PK
    string token_hash UK
    string target_type
    uuid workspace_id FK
    uuid space_id FK
    string role
    uuid created_by_user_id FK
    string status
    timestamptz expires_at
    int max_uses
    int use_count
    timestamptz revoked_at
  }

  share_link_redemptions {
    uuid id PK
    uuid share_link_id FK
    uuid user_id FK
    timestamptz redeemed_at
    string ip_hash
    string user_agent_hash
  }

  confluence_connections {
    uuid id PK
    uuid workspace_id FK
    string name
    string base_url
    string connection_mode
    string auth_type
    string credential_location
    bytes encrypted_credentials
    uuid connector_agent_id FK
    string status
    string detected_version
  }

  connector_agents {
    uuid id PK
    uuid workspace_id FK
    string name
    string agent_key_hash
    string status
    string version
    timestamptz last_heartbeat_at
    jsonb metadata_json
  }

  sources {
    uuid id PK
    uuid workspace_id FK
    uuid space_id FK
    string type
    string name
    string status
    uuid connection_id FK
    string external_type
    string external_id
    string external_url
    string import_scope
  }

  documents {
    uuid id PK
    uuid workspace_id FK
    uuid space_id FK
    uuid source_id FK
    uuid parent_id FK
    string external_id
    string document_type
    string title
    string status
    text raw_content
    text normalized_content
    string content_checksum
  }

  attachments {
    uuid id PK
    uuid workspace_id FK
    uuid space_id FK
    uuid source_id FK
    uuid document_id FK
    string external_id
    string filename
    string media_type
    bigint size_bytes
    string checksum_sha256
    string object_key
  }

  document_chunks {
    uuid id PK
    uuid workspace_id FK
    uuid space_id FK
    uuid source_id FK
    uuid document_id FK
    int chunk_index
    string heading_path
    text content
    int token_count
    string content_hash
    vector embedding
    jsonb metadata_json
  }

  document_versions {
    uuid id PK
    uuid workspace_id FK
    uuid document_id FK
    string external_version
    string content_checksum
    text normalized_content
    timestamptz captured_at
  }

  ingestion_jobs {
    uuid id PK
    uuid workspace_id FK
    uuid space_id FK
    uuid source_id FK
    string job_type
    string status
    float progress_percent
    string stage
    uuid requested_by_user_id FK
    uuid connector_agent_id FK
  }

  ingestion_job_errors {
    uuid id PK
    uuid job_id FK
    string external_item_id
    string item_type
    string error_code
    string error_message_sanitized
    bool retryable
  }

  conversations {
    uuid id PK
    uuid user_id FK
    uuid workspace_id FK
    string title
    string status
  }

  conversation_spaces {
    uuid conversation_id FK
    uuid space_id FK
  }

  messages {
    uuid id PK
    uuid conversation_id FK
    uuid user_id FK
    string role
    text content
    string model_provider
    string model_name
    int input_tokens
    int output_tokens
    jsonb retrieval_metadata_json
  }

  message_space_scope {
    uuid message_id FK
    uuid space_id FK
  }

  citations {
    uuid id PK
    uuid message_id FK
    uuid workspace_id FK
    uuid space_id FK
    uuid source_id FK
    uuid document_id FK
    uuid chunk_id FK
    int citation_index
    string title
    string heading_path
    text snippet
    string source_url
    float retrieval_score
  }

  audit_logs {
    uuid id PK
    uuid workspace_id FK
    uuid actor_user_id FK
    string action
    string resource_type
    uuid resource_id
    jsonb metadata_json_sanitized
  }

  ai_usage {
    uuid id PK
    uuid user_id FK
    uuid workspace_id FK
    uuid conversation_id FK
    uuid message_id FK
    string provider
    string model
    int input_tokens
    int output_tokens
    int request_count
    string status
  }
```

## Key constraints (logical)

| Rule | Enforcement |
|------|-------------|
| Max 10 owned workspaces per user | Transaction-safe count of non-deleted workspaces by `created_by_user_id` |
| Unique active workspace membership | `(workspace_id, user_id)` where `revoked_at IS NULL` |
| Unique active space membership | `(space_id, user_id)` where `revoked_at IS NULL` |
| Unique document external id per source | `(source_id, external_id)` where external_id not null |
| Conversation spaces same workspace | App + DB check: space.workspace_id = conversation.workspace_id |
| Share token | Store `token_hash` only; raw token shown once |
| Vector search | Always filter `workspace_id` (+ space_ids) in query |
