"""Structural OpenAPI contract checks for the frontend handoff.

No external validator is used: the tests assert the documented paths, the
presence of the key schemas and the parts of the contract the frontend relies
on (string money, period and export enums, strict settings payload).
"""

from fastapi.testclient import TestClient

from app.core.config import get_settings

EXPECTED_OPERATIONS = {
    "/api/health": {"get"},
    "/api/portfolio": {"get", "patch"},
    "/api/assets": {"get", "post"},
    "/api/assets/search": {"get"},
    "/api/assets/{asset_id}": {"get", "delete"},
    "/api/assets/{asset_id}/refresh": {"post"},
    "/api/operations": {"get", "post"},
    "/api/operations/{operation_id}": {"patch", "delete"},
    "/api/positions": {"get"},
    "/api/income": {"get", "post"},
    "/api/income/{income_id}": {"patch", "delete"},
    "/api/income/{income_id}/mark-paid": {"post"},
    "/api/quotes/{asset_id}/history": {"get"},
    "/api/quotes/refresh": {"post"},
    "/api/quotes/manual": {"post"},
    "/api/dashboard": {"get"},
    "/api/snapshots": {"get"},
    "/api/settings": {"get", "patch"},
    "/api/backup": {"post"},
    "/api/export": {"get"},
}

REQUIRED_SCHEMAS = {
    "DashboardResponse",
    "DashboardTotalsOut",
    "DashboardSeriesPointOut",
    "PositionItem",
    "IncomeItem",
    "SettingsResponse",
    "BackupResponse",
    "SnapshotListResponse",
    "ValidationError",
}

MONEY_FIELDS = (
    "market_value",
    "invested",
    "dividends_paid",
    "coupons_paid",
    "income_paid_total",
    "expected_coupons",
)

STRING_MONEY_FIELDS = {
    "PositionItem": (
        "avg_price",
        "avg_price_percent",
        "current_price",
        "current_face_value",
        "market_value",
        "invested",
        "share",
    ),
    "IncomeItem": ("amount_per_unit", "amount_total"),
    "OperationResponse": ("input_price", "price_rub"),
    "AssetDetail": ("initial_face_value", "current_face_value"),
    "SnapshotItem": ("market_value", "invested", "income_paid"),
}


def _schema(client: TestClient) -> dict:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    return response.json()


def _is_string_schema(schema: dict) -> bool:
    """Return true for ``str`` or an optional ``str | None`` variant."""

    if schema.get("type") == "string":
        return True
    return any(variant.get("type") == "string" for variant in schema.get("anyOf", []))


def _enum_values(node: object) -> set:
    values: set = set()

    def walk(value: object) -> None:
        if isinstance(value, dict):
            enum = value.get("enum")
            if isinstance(enum, list):
                values.update(enum)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(node)
    return values


def test_openapi_metadata(client: TestClient) -> None:
    schema = _schema(client)

    assert schema["openapi"].startswith("3.")
    assert schema["info"]["version"] == get_settings().app_version


def test_all_documented_paths_and_methods_are_present(client: TestClient) -> None:
    schema = _schema(client)
    paths = schema["paths"]

    assert set(paths) == set(EXPECTED_OPERATIONS)
    for path, methods in EXPECTED_OPERATIONS.items():
        assert set(paths[path]) == methods, path


def test_operation_ids_are_unique(client: TestClient) -> None:
    schema = _schema(client)

    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    ]

    assert operation_ids
    assert all(operation_ids)
    assert len(operation_ids) == len(set(operation_ids))


def test_key_schemas_exist(client: TestClient) -> None:
    components = _schema(client)["components"]["schemas"]

    assert set(components) >= REQUIRED_SCHEMAS


def test_money_is_documented_as_strings(client: TestClient) -> None:
    components = _schema(client)["components"]["schemas"]
    totals = components["DashboardTotalsOut"]["properties"]
    series = components["DashboardSeriesPointOut"]["properties"]

    for field in MONEY_FIELDS:
        assert totals[field]["type"] == "string"
    assert series["market_value"]["type"] == "string"
    assert series["invested"]["type"] == "string"

    for schema_name, fields in STRING_MONEY_FIELDS.items():
        properties = components[schema_name]["properties"]
        for field in fields:
            assert _is_string_schema(properties[field]), f"{schema_name}.{field}"

    settings = components["SettingsResponse"]["properties"]
    assert settings["quote_refresh_enabled"]["type"] == "boolean"


def test_dashboard_period_enum(client: TestClient) -> None:
    schema = _schema(client)
    period = next(
        parameter
        for parameter in schema["paths"]["/api/dashboard"]["get"]["parameters"]
        if parameter["name"] == "period"
    )

    assert _enum_values(period["schema"]) == {"1M", "3M", "1Y", "ALL"}


def test_export_format_enum(client: TestClient) -> None:
    schema = _schema(client)
    export_format = next(
        parameter
        for parameter in schema["paths"]["/api/export"]["get"]["parameters"]
        if parameter["name"] == "format"
    )

    assert _enum_values(export_format["schema"]) == {"json", "csv"}


def test_settings_patch_rejects_unknown_keys(client: TestClient) -> None:
    components = _schema(client)["components"]["schemas"]

    update = components["SettingsUpdate"]
    assert update["additionalProperties"] is False
    assert set(update["properties"]) == {"quote_refresh_enabled", "dashboard_period"}
