"""Pure unit tests for Space role helpers (no database)."""

from app.models.space import SpaceRole


def test_space_role_rank() -> None:
    assert SpaceRole.at_least(SpaceRole.OWNER, SpaceRole.VIEWER)
    assert SpaceRole.at_least(SpaceRole.EDITOR, SpaceRole.VIEWER)
    assert not SpaceRole.at_least(SpaceRole.VIEWER, SpaceRole.EDITOR)
    assert not SpaceRole.at_least(SpaceRole.EDITOR, SpaceRole.OWNER)


def test_space_role_strongest() -> None:
    assert SpaceRole.strongest(SpaceRole.VIEWER, SpaceRole.EDITOR) == SpaceRole.EDITOR
    assert SpaceRole.strongest(SpaceRole.OWNER, SpaceRole.VIEWER) == SpaceRole.OWNER
    assert SpaceRole.strongest(None, SpaceRole.VIEWER) == SpaceRole.VIEWER
    assert SpaceRole.strongest(None, None) is None
