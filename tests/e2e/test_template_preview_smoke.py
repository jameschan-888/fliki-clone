"""Fast live-HTTP smoke for template field validation and resolved render plans."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


BASE = os.environ.get("FLIKI_BASE", "http://127.0.0.1:5181").rstrip("/")


def http(method, path, data=None):
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data is not None else None
    request = urllib.request.Request(
        BASE + path,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"raw": raw}
        return error.code, payload


def sample_fields(template):
    values = {}
    for field in template.get("fields", []):
        key = field["key"]
        default = field.get("default")
        field_type = field.get("type", "text")
        if default not in (None, ""):
            value = default
        elif field_type == "number":
            value = field.get("min", 1)
        elif field_type == "select" and field.get("options"):
            option = field["options"][0]
            value = option if isinstance(option, str) else option["value"]
        else:
            max_length = int(field.get("max_length") or 80)
            value = ("smoke-" + key)[:max_length]
        values[key] = value
    return values


def main():
    health_status, health = http("GET", "/health")
    assert health_status == 200, f"health failed: {health_status} {health}"

    status, templates = http("GET", "/templates?enabled_only=true&include_config=true")
    assert status == 200, f"template list failed: {status} {templates}"
    assert isinstance(templates, list) and len(templates) >= 5, templates

    rendered_ids = []
    for template in templates:
        template_id = template["id"]
        fields = sample_fields(template)
        status, preview = http(
            "POST",
            "/templates/" + urllib.parse.quote(template_id, safe="") + "/preview",
            {"fields": fields, "duration_seconds": 1.0},
        )
        assert status == 200, f"preview {template_id} failed: {status} {preview}"
        assert preview["ok"] is True and preview["preview"] is True, preview
        assert preview["mock"] is True, preview
        plan = preview["plan"]
        assert plan["template_id"] == template_id, plan
        assert plan["provider"] == "mock", plan
        assert plan["duration_seconds"] == 1.0, plan
        expected_layers = len(template.get("structure", {}).get("layers", []))
        assert plan["layer_count"] == expected_layers and expected_layers > 0, plan
        unresolved = [
            layer.get("text")
            for layer in plan["layers"]
            if isinstance(layer.get("text"), str)
            and layer["text"].startswith("{")
            and layer["text"].endswith("}")
        ]
        assert not unresolved, f"{template_id} unresolved fields: {unresolved}"
        rendered_ids.append(template_id)
        print(f"PREVIEW {template_id} layers={plan['layer_count']} fields={len(preview['merged_fields'])}")

    invalid_status, invalid = http(
        "POST",
        "/templates/intro_simple/preview",
        {"fields": {}, "duration_seconds": 1.0},
    )
    assert invalid_status == 422, f"invalid fields should fail: {invalid_status} {invalid}"
    assert "title is required" in json.dumps(invalid, ensure_ascii=False), invalid

    print("RESULT " + json.dumps({"templates": rendered_ids, "count": len(rendered_ids)}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print("FAIL " + str(error))
        sys.exit(1)
    except Exception as error:
        print("ERROR " + type(error).__name__ + ": " + str(error))
        sys.exit(2)
    print("PASS")
