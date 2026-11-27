from datetime import date

from app.modules.users.audit_repository import SecurityAuditRepository
from app.modules.users.repository import UserRepository
from app.modules.users.service import UserService


def test_gender_values_are_optional_and_normalized():
    assert UserService.validate_gender(None) == (None, None)
    assert UserService.validate_gender("  non-BINARY ") == ("Non-binary", None)
    for gender in ("Male", "Female", "Non-binary", "Prefer not to say", "Other"):
        assert UserService.validate_gender(gender) == (gender, None)
    assert UserService.validate_gender("unspecified")[1] == "Select a valid gender option"


def test_age_groups_cover_all_requested_ranges():
    cases = [
        (17, "under_18"),
        (18, "18_25"),
        (25, "18_25"),
        (26, "26_35"),
        (35, "26_35"),
        (36, "36_45"),
        (45, "36_45"),
        (46, "46_60"),
        (60, "46_60"),
        (61, "over_60"),
    ]

    for age, expected in cases:
        assert UserService._age_group_from_age(age) == expected


def test_avatar_profile_uses_existing_age_only_when_birth_date_has_no_group():
    profile = UserService._new_avatar_profile("Female", age=36)
    assert profile["gender"] == "Female"
    assert profile["age_group"] == "36_45"

    today = date.today()
    birth_date = date(today.year - 30, 1, 1)
    profile = UserService._new_avatar_profile("Male", birth_date, age=61)
    assert profile["age_group"] == "26_35"


def test_update_without_gender_does_not_overwrite_existing_gender(monkeypatch):
    stored_updates = {}
    user = {"user_id": "employee-1", "name": "Old Name", "gender": "Female"}

    monkeypatch.setattr(
        UserRepository,
        "find_by_id",
        staticmethod(lambda user_id, organization_id=None: user),
    )
    monkeypatch.setattr(
        UserRepository,
        "update_user",
        staticmethod(lambda user_id, organization_id, update_fields: stored_updates.update(update_fields) or True),
    )
    monkeypatch.setattr(
        SecurityAuditRepository,
        "log_event",
        staticmethod(lambda **kwargs: None),
    )
    monkeypatch.setattr(
        UserService,
        "get_user_by_id",
        staticmethod(lambda user_id, organization_id: {"success": True, "data": user}),
    )

    result = UserService.update_user(
        "employee-1",
        "organization-1",
        {"name": "New Name"},
        actor_id="admin-1",
    )

    assert result["success"] is True
    assert stored_updates["name"] == "New Name"
    assert "gender" not in stored_updates


def test_avatar_refresh_uses_updated_gender_and_existing_age(monkeypatch):
    stored_updates = {}
    user = {"user_id": "employee-1", "name": "Employee", "gender": "Female", "age": 36}

    monkeypatch.setattr(
        UserRepository,
        "find_by_id",
        staticmethod(lambda user_id, organization_id=None: user),
    )
    monkeypatch.setattr(
        UserRepository,
        "update_user",
        staticmethod(lambda user_id, organization_id, update_fields: stored_updates.update(update_fields) or True),
    )
    monkeypatch.setattr(
        SecurityAuditRepository,
        "log_event",
        staticmethod(lambda **kwargs: None),
    )
    monkeypatch.setattr(
        UserService,
        "get_user_by_id",
        staticmethod(lambda user_id, organization_id: {"success": True, "data": user}),
    )

    UserService.update_user(
        "employee-1",
        "organization-1",
        {"gender": "Male", "refresh_avatar": True},
        actor_id="admin-1",
    )

    assert stored_updates["gender"] == "Male"
    assert stored_updates["avatar_profile"]["gender"] == "Male"
    assert stored_updates["avatar_profile"]["age_group"] == "36_45"
