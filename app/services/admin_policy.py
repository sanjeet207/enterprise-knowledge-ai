"""What a portal administrator may grant. Plain code, so the rule is easy to read and test.

An administrator manages people and documents but is not meant to read restricted content. Without a ceiling an
administrator could create or promote an account to level 4, reset its password, sign in as it and read everything
(separation of duties). So grants are capped, and passwords of higher-level accounts cannot be reset by an
administrator. Higher levels come from the identity provider (group mapping) or from IT security, and revoking
access (lowering a level, switching an account off) is always allowed.
"""
from typing import Optional


def check_grant(max_grant: int, new_level: Optional[int], target_level: Optional[int], changing_password: bool) -> None:
    """Raises PermissionError with a message that is safe to show. target_level is None for a new account."""
    if new_level is not None and new_level > max_grant:
        raise PermissionError(f"Administrators can grant reading levels up to {max_grant}. "
                              "Higher levels are granted by IT security or through the identity provider.")
    if changing_password and target_level is not None and target_level > max_grant:
        raise PermissionError(f"Administrators cannot reset the password of an account above level {max_grant}.")
