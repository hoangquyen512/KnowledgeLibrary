export type ConfluenceConnection = {
  id: string;
  workspace_id: string;
  name: string;
  base_url: string;
  connection_mode: string;
  credential_location: string;
  connector_agent_id: string | null;
  auth_type: string;
  masked_suffix: string;
  status: string;
  detected_version: string | null;
  last_tested_at: string | null;
  last_error: string | null;
  source_count?: number;
};
