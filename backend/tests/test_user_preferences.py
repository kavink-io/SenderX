import uuid
from flask_jwt_extended import create_access_token

from app.modules.auth.repository import AuthRepository
from app.modules.organizations.repository import OrganizationRepository
from app.modules.users.repository import UserRepository
from app.modules.users.preferences_repository import UserPreferencesRepository


def _seed_org_user(app, org_id, email, name="User"):
    user_id = str(uuid.uuid4())
    with app.app_context():
        if not OrganizationRepository.find_by_id(org_id):
            OrganizationRepository.create({
                "organization_id": org_id,
                "name": f"Org {org_id}",
                "slug": f"org-{org_id[:8]}",
                "status": "ACTIVE",
            })
        UserRepository.create({
            "user_id": user_id,
            "organization_id": org_id,
            "email": email,
            "name": name,
            "password_hash": "$2b$04$dummyhashfortestingonly12345678901234567890",
            "role_ids": [],
            "is_active": True,
            "status": "ACTIVE",
            "token_version": 1,
        })
        token = create_access_token(
            identity=user_id,
            additional_claims={
                "account_type": "ORGANIZATION_USER",
                "organization_id": org_id,
                "token_version": 1,
            },
        )
    return user_id, token


def test_preferences_require_authentication(client):
    for method in (client.get, client.put, client.patch):
        resp = method("/api/v1/users/me/preferences", json={"appearance": {"theme_mode": "dark"}})
        assert resp.status_code == 401


def test_preferences_per_user_and_per_org_isolation(app, client):
    org_a = f"org-a-{uuid.uuid4().hex[:6]}"
    org_b = f"org-b-{uuid.uuid4().hex[:6]}"

    user_a1, token_a1 = _seed_org_user(app, org_a, f"a1-{uuid.uuid4().hex[:6]}@example.com", "Alice")
    user_a2, token_a2 = _seed_org_user(app, org_a, f"a2-{uuid.uuid4().hex[:6]}@example.com", "Bob")
    user_b1, token_b1 = _seed_org_user(app, org_b, f"b1-{uuid.uuid4().hex[:6]}@example.com", "Charlie")

    headers_a1 = {"Authorization": f"Bearer {token_a1}"}
    headers_a2 = {"Authorization": f"Bearer {token_a2}"}
    headers_b1 = {"Authorization": f"Bearer {token_b1}"}

    # Default preferences for fresh user
    get_a1 = client.get("/api/v1/users/me/preferences", headers=headers_a1)
    assert get_a1.status_code == 200
    body_a1 = get_a1.get_json()
    assert body_a1["success"] is True
    assert body_a1["data"]["appearance"]["theme_mode"] == "light"
    assert body_a1["data"]["layout"]["density"] == "comfortable"

    # Alice saves custom theme, accent color, density, typography & layout via PATCH
    patch_a1 = client.patch(
        "/api/v1/users/me/preferences",
        headers=headers_a1,
        json={
            "appearance": {
                "theme_mode": "dark",
                "accent_color": "#e11d48",
                "font_family": "mono",
                "font_scale": "large",
            },
            "layout": {
                "direction": "rtl",
                "navigation_layout": "horizontal",
                "sidebar_mode": "collapsed",
                "sidebar_position": "sticky",
                "sidebar_collapsible": False,
                "density": "compact",
            },
        },
    )
    assert patch_a1.status_code == 200
    saved_a1 = patch_a1.get_json()["data"]
    assert saved_a1["appearance"] == {
        "theme_mode": "dark",
        "accent_color": "#E11D48",
        "font_family": "mono",
        "font_scale": "large",
    }
    assert saved_a1["layout"] == {
        "direction": "rtl",
        "navigation_layout": "horizontal",
        "sidebar_mode": "collapsed",
        "sidebar_position": "sticky",
        "sidebar_collapsible": False,
        "density": "compact",
    }
    assert saved_a1["updated_at"] is not None

    # Bob in the SAME organization keeps defaults until saving his own
    get_a2 = client.get("/api/v1/users/me/preferences", headers=headers_a2)
    assert get_a2.status_code == 200
    assert get_a2.get_json()["data"]["appearance"]["theme_mode"] == "light"
    assert get_a2.get_json()["data"]["layout"]["direction"] == "ltr"

    # Bob updates only his preferences
    patch_a2 = client.patch(
        "/api/v1/users/me/preferences",
        headers=headers_a2,
        json={"appearance": {"theme_mode": "system", "accent_color": "#059669"}},
    )
    assert patch_a2.status_code == 200

    # Charlie in ANOTHER organization is untouched
    get_b1 = client.get("/api/v1/users/me/preferences", headers=headers_b1)
    assert get_b1.status_code == 200
    assert get_b1.get_json()["data"]["appearance"]["theme_mode"] == "light"

    # Re-fetch Alice to confirm Bob & Charlie never affected her saved document
    reget_a1 = client.get("/api/v1/users/me/preferences", headers=headers_a1)
    assert reget_a1.status_code == 200
    assert reget_a1.get_json()["data"]["appearance"]["theme_mode"] == "dark"
    assert reget_a1.get_json()["data"]["appearance"]["accent_color"] == "#E11D48"

    # Verify DB stores per-user records cleanly
    with app.app_context():
        doc_a1 = UserPreferencesRepository.find_by_user(user_a1, org_a)
        doc_a2 = UserPreferencesRepository.find_by_user(user_a2, org_a)
        assert doc_a1["user_id"] == user_a1
        assert doc_a2["user_id"] == user_a2
        assert doc_a1["appearance"]["theme_mode"] == "dark"
        assert doc_a2["appearance"]["theme_mode"] == "system"


def test_preferences_cross_user_tamper_and_validation_rejected(app, client):
    org_id = f"org-val-{uuid.uuid4().hex[:6]}"
    user_a, token_a = _seed_org_user(app, org_id, f"va-{uuid.uuid4().hex[:6]}@example.com")
    user_b, _ = _seed_org_user(app, org_id, f"vb-{uuid.uuid4().hex[:6]}@example.com")
    headers = {"Authorization": f"Bearer {token_a}"}

    # Cannot target another user_id
    resp = client.put(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"user_id": user_b, "appearance": {"theme_mode": "dark"}},
    )
    assert resp.status_code == 403

    # Cannot target another organization_id
    resp = client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"organization_id": "other-org", "appearance": {"theme_mode": "dark"}},
    )
    assert resp.status_code == 403

    # Invalid hex, enum, boolean, unknown field
    invalid_payloads = [
        {"appearance": {"accent_color": "red"}},
        {"appearance": {"theme_mode": "neon"}},
        {"appearance": {"font_scale": "giant"}},
        {"layout": {"density": "ultra-dense"}},
        {"layout": {"sidebar_collapsible": "yes"}},
        {"appearance": {"unknown_key": "value"}},
        {},
    ]
    for bad in invalid_payloads:
        r = client.patch("/api/v1/users/me/preferences", headers=headers, json=bad)
        assert r.status_code == 400


def test_preferences_put_replaces_and_patch_merges(app, client):
    org_id = f"org-put-{uuid.uuid4().hex[:6]}"
    _, token = _seed_org_user(app, org_id, f"put-{uuid.uuid4().hex[:6]}@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    r1 = client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={
            "appearance": {"theme_mode": "dark", "accent_color": "#2563EB"},
            "layout": {"density": "spacious", "direction": "rtl"},
        },
    )
    assert r1.status_code == 200

    # PUT replaces full preferences with defaults merged with payload
    r2 = client.put(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"appearance": {"theme_mode": "system"}},
    )
    assert r2.status_code == 200
    data = r2.get_json()["data"]
    assert data["appearance"]["theme_mode"] == "system"
    assert data["appearance"]["accent_color"] == "#635BDB"
    assert data["layout"]["direction"] == "ltr"
    assert data["layout"]["density"] == "comfortable"


def test_platform_admin_can_persist_own_preferences(app, client):
    admin_id = f"admin-{uuid.uuid4().hex[:8]}"
    email = f"admin-{uuid.uuid4().hex[:6]}@senderx.local"
    with app.app_context():
        AuthRepository.create_admin({
            "admin_id": admin_id,
            "email": email,
            "name": "Super Admin",
            "password_hash": "$2b$04$dummyhashfortestingonly12345678901234567890",
            "role": "SUPER_ADMIN",
            "is_active": True,
            "token_version": 1,
        })
        token = create_access_token(
            identity=admin_id,
            additional_claims={"account_type": "PLATFORM_ADMIN", "token_version": 1},
        )

    headers = {"Authorization": f"Bearer {token}"}
    res = client.patch(
        "/api/v1/users/me/preferences",
        headers=headers,
        json={"appearance": {"theme_mode": "dark"}, "layout": {"sidebar_mode": "collapsed"}},
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["appearance"]["theme_mode"] == "dark"
    assert res.get_json()["data"]["layout"]["sidebar_mode"] == "collapsed"
