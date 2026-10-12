export type PagePermissions = {
  can_view: boolean;
  can_edit: boolean;
  can_move: boolean;
  can_archive: boolean;
  can_delete: boolean;
  can_sync: boolean;
  can_create_child: boolean;
};

export type PageTreeNode = {
  id: string;
  title: string;
  has_children: boolean;
  child_count: number;
  status: string;
  origin: string;
  parent_id: string | null;
  position: number;
  depth: number;
};

export type PagePathItem = { id: string; title: string };

export type PageDetail = {
  id: string;
  workspace_id: string;
  space_id: string;
  source_id: string | null;
  parent_id: string | null;
  title: string;
  status: string;
  origin: string;
  position: number;
  depth: number;
  external_id: string | null;
  external_version: string | null;
  external_url: string | null;
  has_children: boolean;
  child_count: number;
  is_starred: boolean;
  created_at: string;
  updated_at: string;
  permissions: PagePermissions;
  ancestors: PagePathItem[];
  raw_content: string | null;
  normalized_content: string | null;
};

export type PageSearchHit = {
  id: string;
  title: string;
  path: string[];
  status: string;
  origin: string;
  match_field?: "title" | "content" | string;
  snippet?: string | null;
};
