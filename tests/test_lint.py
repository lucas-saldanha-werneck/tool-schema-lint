import json
from pathlib import Path

from tool_schema_lint import lint_tools, load_tools
from tool_schema_lint.cli import main

EX = Path(__file__).parent.parent / "examples" / "example-tools.json"


def rules(tools, **kw):
    return {(f.rule, f.tool) for f in lint_tools(load_tools(tools), **kw)}


def tool(name="get_weather", desc="Get the current weather for a city name.", props=None, required=None):
    schema = {"type": "object", "properties": props or {}}
    if required is not None:
        schema["required"] = required
    return {"name": name, "description": desc, "input_schema": schema}


GOOD = {"city": {"type": "string", "description": "City name"}}


def test_clean_tool_has_no_findings():
    assert rules([tool(props=GOOD, required=["city"])]) == set()


def test_vague_name():
    assert ("TS001", "run") in rules([tool(name="run", props=GOOD, required=["city"])])


def test_numbered_name():
    assert ("TS001", "tool_2") in rules([tool(name="tool_2", props=GOOD, required=["city"])])


def test_short_description():
    assert ("TS002", "get_weather") in rules([tool(desc="Weather", props=GOOD, required=["city"])])


def test_param_without_description():
    r = rules([tool(props={"city": {"type": "string"}}, required=["city"])])
    assert ("TS003", "get_weather") in r


def test_enum_like_string():
    p = {"status": {"type": "string", "description": "x"}}
    assert ("TS004", "get_weather") in rules([tool(props=p, required=["status"])])
    p["status"]["enum"] = ["open", "closed"]
    assert ("TS004", "get_weather") not in rules([tool(props=p, required=["status"])])


def test_missing_required_list():
    assert ("TS005", "get_weather") in rules([tool(props=GOOD)])


def test_required_not_in_properties():
    assert ("TS006", "get_weather") in rules([tool(props=GOOD, required=["city", "unit"])])


def test_mutating_without_idempotency_key():
    r = rules([tool(name="send_email", desc="Send an email to one recipient now.", props=GOOD, required=["city"])])
    assert ("TS007", "send_email") in r
    p = dict(GOOD, idempotency_key={"type": "string", "description": "k"})
    r = rules([tool(name="send_email", desc="Send an email to one recipient now.", props=p, required=["city"])])
    assert ("TS007", "send_email") not in r


def test_duplicate_names():
    t = tool(props=GOOD, required=["city"])
    assert ("TS008", "get_weather") in rules([t, t])


def test_overlapping_descriptions():
    a = tool("find_user", "Find a user record by email address or id.", GOOD, ["city"])
    b = tool("lookup_user", "Find a user record by email address or id number.", GOOD, ["city"])
    assert ("TS009", "find_user") in rules([a, b])
    c = tool("get_weather", "Get the current weather for a city name.", GOOD, ["city"])
    assert not any(r == "TS009" for r, _ in rules([a, c]))


def test_openai_format_is_read():
    t = {"type": "function", "function": {"name": "get_weather", "description": "Get the current weather for a city.",
         "parameters": {"type": "object", "properties": GOOD, "required": ["city"]}}}
    assert rules([t]) == set()


def test_example_file_findings():
    r = rules(json.loads(EX.read_text()))
    assert ("TS009", "search_orders") in r
    assert ("TS001", "run") in r
    assert ("TS006", "refund_order") in r
    assert ("TS007", "refund_order") in r
    assert ("TS004", "set_ticket") in r


def test_cli_exit_codes(tmp_path, capsys):
    assert main([str(EX)]) == 1
    assert main([str(EX), "--fail-on", "never"]) == 0
    capsys.readouterr()
    ok = tmp_path / "ok.json"
    ok.write_text(json.dumps([tool(props=GOOD, required=["city"])]))
    assert main([str(ok)]) == 0
    assert main([str(tmp_path / "missing.json")]) == 2


def test_cli_json_output(capsys):
    main([str(EX), "--json", "--fail-on", "never"])
    data = json.loads(capsys.readouterr().out)
    assert any(f["rule"] == "TS006" for f in data)
