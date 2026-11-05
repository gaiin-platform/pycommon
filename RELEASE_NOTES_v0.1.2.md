# pycommon v0.1.2

**Release Date**: 2026-11-06 (planned), shipped with Amplify v0.9.5
**Previous Version**: v0.1.1
**Used by**: every Python service in [`amplify-genai-backend`](https://github.com/gaiin-platform/amplify-genai-backend). See its `RELEASE_NOTES_NEW_UI.md` for the deploy order.

> **Version labels.** `v0.1.2` is currently a **Git branch** of this repository, not a tag, and `pyproject.toml` still says `version = "0.1.0"`. `pip install git+https://github.com/gaiin-platform/pycommon.git@v0.1.2` installs whatever commit the branch points at when you run it. To record what you built, note the commit:
> ```bash
> git ls-remote https://github.com/gaiin-platform/pycommon.git refs/heads/v0.1.2
> ```

## What changed from v0.1.1 (9 commits)

| Area | Change | Who is affected |
|---|---|---|
| Parameter Store | New `pycommon.deployment.parameter_store_sync.cfn_handler`, a CloudFormation custom-resource handler. | Every backend stack. |
| LZW compression | Unicode fix (see below). | Anything that reads or writes compressed conversations or payloads. |
| Rate limits | Clearer error messages for rate-limit responses; new helper `get_rate_limit_notice()` (no backend service calls it yet). | Callers of `pycommon.llm.chat` / API helpers. |
| Chat | `delta_text()` handles dict-shaped stream deltas instead of raising. | LLM streaming callers. |
| Accounting | `MODEL_RATE_TABLE` is required only when no `flat_cost` is given. Model-cost fields and docs for additional charges updated. | Services recording costs. |
| Auth | JWT verification uses PyJWT instead of `python-jose`. Same checks: RS256 signature, issuer, audience (if the token has one), access-token type. | Every service using `@validated`. |
| Dependencies | Python **3.11+** required (was 3.8+). `python-jose` removed; `PyJWT[crypto]`, `certifi`, `PyYAML`, `urllib3` added; minimum versions raised for `boto3`, `botocore`, `pydantic`, `requests`, `python-dotenv`, `jsonschema`. | Any project that pins older versions of those packages. |

### Parameter Store handler (`cfn_handler`)

- Used as the Lambda handler of a stack's `param_populator` function, behind a `Custom::ParamStorePopulate` resource.
- Reads `SERVICE_NAME` and `STAGE` from the Lambda's **own environment**; both must be set and `SERVICE_NAME` must equal the stack's `service:` name.
- Writes every environment variable whose value starts with `<SERVICE_NAME>-<STAGE>-` (skipping `AWS_*`) to SSM at `/amplify/<STAGE>/<SERVICE_NAME>/<VARIABLE>`.
- The role needs `ssm:GetParameter` and `ssm:PutParameter` on `/amplify/<STAGE>/<SERVICE_NAME>/*`.
- The custom-resource properties (`ServiceName`, `Stage`) are ignored; `TriggerHash` only forces an update on each deploy.
- Delete is a no-op that reports success, so parameters are kept when a stack is removed. A failure to write one parameter is reported as success with an error count; only missing environment variables or a top-level error report failure.

### LZW unicode fix

- **Before**: Python wrote `U+` plus a 4-digit code point, so emoji (5 digits) were read back as garbage. JavaScript wrote unpadded hex, so U+0100-U+0FFF (Cyrillic, Greek, Hebrew, Arabic, Thai) got 3-digit tags that could not be read. Typed text such as `U+0041` was read back as `A`.
- **Now**: every UTF-16 code unit above 255 is written as `U+` plus exactly 4 lowercase hex digits (an emoji becomes two tags), a literal `U+` is escaped, and the old 3-digit tags are still read when no hex digit follows. The Python, backend JavaScript and frontend implementations share one set of test vectors (`tests/fixtures/lzw_vectors.json`).
- **Compatibility**: new code reads data written by old code, except data that was already unreadable (emoji written by the old Python encoder, or a 3-digit tag followed by a hex character). Old code reads new data correctly for ordinary text and BMP scripts; an old Python reader returns two lone surrogate characters for an emoji.
- **Operators**: deploy all Python services on v0.1.2, and the frontend and backend of Amplify v0.9.5, together. No stored data needs to be migrated.

## Upgrading a project that depends on pycommon

1. Update the pin to `git+https://github.com/gaiin-platform/pycommon.git@v0.1.2`.
2. Check your own pins against the new minimums: `certifi>=2026.10.23`, `PyJWT[crypto]>=2.15.1`, `PyYAML>=6.0.3`, `urllib3>=2.8.0`, `boto3`/`botocore>=1.43.100`, `pydantic>=2.13.5`, `requests>=2.34.2`. An older exact pin (for example `certifi==2025.6.15`) makes `pip` fail to resolve.
3. If your code did `import jose` and relied on `python-jose` arriving through pycommon, add `python-jose` to your own requirements or move to PyJWT. pycommon no longer installs it.
4. Make sure build machines can reach GitHub.

## Not verified

We read the diff and ran no pycommon test suite or deployment for this note.
