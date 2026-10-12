from app.models.workspace import WorkspaceRole
from app.settings.service import ALLOWED_THEMES


def test_workspace_role_rank() -> None:
    assert WorkspaceRole.at_least(WorkspaceRole.OWNER, WorkspaceRole.VIEWER)
    assert WorkspaceRole.at_least(WorkspaceRole.EDITOR, WorkspaceRole.VIEWER)
    assert not WorkspaceRole.at_least(WorkspaceRole.VIEWER, WorkspaceRole.EDITOR)
    assert WorkspaceRole.at_least(WorkspaceRole.OWNER, WorkspaceRole.OWNER)


def test_theme_allowed_values() -> None:
    assert ALLOWED_THEMES == {"LIGHT", "DARK", "SYSTEM"}
