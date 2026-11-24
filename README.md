# tool-schema-lint

Independent demo, not affiliated with BairesDev.

A small command-line tool that reads the tool definitions you give an LLM agent and lists the ones likely to cause trouble. It works offline, uses only the Python standard library, and reads both Anthropic (`input_schema`) and OpenAI (`type: function`) formats.

I wrote it because agent bugs often start in the tool list, not in the model. Two tools with near-identical descriptions make routing a coin flip. A parameter marked `required` that does not exist can never be filled. A "send" tool with no idempotency key runs twice when the agent retries.

## Run it

```
uv sync
uv run tool-schema-lint examples/example-tools.json
uv run tool-schema-lint tools.json --json --fail-on warn
```

Exit code is 1 when a finding at or above `--fail-on` exists (default `error`), 2 when the file cannot be read, 0 otherwise. `--overlap 0.6` sets how similar two descriptions must be to get flagged.

## Rules

| Rule | Level | Checks |
|---|---|---|
| TS001 | warn | Vague name (`run`, `handle`, `tool_2`) |
| TS002 | error | Description missing or under 5 words |
| TS003 | warn | Parameter without a description |
| TS004 | warn | Free string named `status`, `type`, `mode`... that should be an enum |
| TS005 | warn | Parameters but no `required` list |
| TS006 | error | `required` names a parameter that is not defined |
| TS007 | info | State-changing tool (`send_`, `refund_`, `delete_`...) without an idempotency key |
| TS008 | error | Same tool name defined twice |
| TS009 | warn | Two descriptions share most of their words |

## What was tested

- 15 pytest tests, run offline: each rule fires on a bad case and stays quiet on a good one, both input formats load, the CLI exit codes and `--json` output work.
- The same tests run in GitHub Actions on every push (`.github/workflows/test.yml`).
- `examples/example-tools.json` is invented example data. On it the tool reports 10 findings, including a `required` entry (`reason`) with no matching property and two order-lookup tools that overlap 88%.

## What was not tested

- No real agent or model was run. I did not measure whether fixing a finding improves tool choice.
- No real product's tool list was checked.
- TS004, TS007 and TS009 are word-list and word-overlap heuristics. They will miss cases and will flag some fine tools. Treat them as prompts to look, not verdicts.
- Nested schemas (`$ref`, `oneOf`, arrays of objects) are not inspected; only top-level properties are.
- Tested on Python 3.15 locally and on whatever `ubuntu-latest` provides in CI.
