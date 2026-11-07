"""Who may add a document, and where. Written as plain code so the rule is easy to read and test.

Portal administrators (the knowledge-management team) publish company-wide documents at any level.
Managers and above may add documents only to an engagement workspace they belong to, and not above their own level.
Everyone else cannot upload.
"""
from typing import Optional


def check_upload(is_admin: bool, user_level: int, level: int, engagement_id: Optional[str], is_member: bool) -> None:
    """Raises PermissionError with a message that is safe to show to the person."""
    if is_admin:
        return
    if user_level < 2:
        raise PermissionError("Your role cannot add documents")
    if not engagement_id:
        raise PermissionError("Choose the engagement team this document belongs to. Company-wide documents are published by the administrators")
    if not is_member:
        raise PermissionError("You can only add documents to engagements you belong to")
    if level > user_level:
        raise PermissionError("You cannot classify a document above your own level")


def can_delete(is_admin: bool, user_id: str, uploaded_by_id: Optional[str]) -> bool:
    return is_admin or (uploaded_by_id is not None and uploaded_by_id == user_id)
