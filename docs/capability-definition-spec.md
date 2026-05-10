# Capability Definition Spec

## Goal

Provide a stable external definition format for capabilities so the runtime registry can load them from disk without introducing a second provider integration path.

## Directories

- Workflow definitions: `capabilities/workflows/`
- Tool definitions: `capabilities/tools/`

Both directories are configurable through:

- `CAPABILITIES_DIR`
- `WORKFLOW_DEFINITIONS_DIR`
- `TOOL_DEFINITIONS_DIR`

## Workflow Definition Format

Workflow definitions are JSON files loaded from `capabilities/workflows/*.json`.

### Required Fields

- `name`
- `description`
- `parameters`
- `steps`
- `finalizer`

### Supported Optional Fields

- `providers`
- `risk_level`
- `category`

### Step Argument Sources (Schema v2)

Each step can still use legacy `arguments_from_input`, or use the richer `arguments` object.

Supported `arguments` sources:

- `input`: map from workflow input parameters
- `constant`: inject a fixed value
- `step_output`: read from a previous step result

### Schema v2 Example

```json
{
  "name": "workflow_send_skill_preview",
  "description": "读取 skill 后把正文发回当前会话。",
  "category": "workflows",
  "providers": ["claude", "openai"],
  "risk_level": "write",
  "parameters": {
    "type": "object",
    "properties": {
      "name": {"type": "string", "description": "skill 名称"}
    },
    "required": ["name"]
  },
  "steps": [
    {
      "name": "preview",
      "tool_name": "read_skill",
      "arguments": {
        "name": {"source": "input", "name": "name"}
      }
    },
    {
      "name": "send",
      "tool_name": "send_message",
      "arguments": {
        "text": {"source": "step_output", "step": "preview", "path": "text"}
      }
    }
  ],
  "finalizer": "last_step_text"
}
```

### Legacy Example

```json
{
  "name": "workflow_update_skill_with_preview",
  "description": "更新 skill 元数据或正文后，自动返回最新完整内容。",
  "category": "workflows",
  "providers": ["claude", "openai"],
  "risk_level": "write",
  "parameters": {
    "type": "object",
    "properties": {
      "name": {"type": "string", "description": "skill 名称"},
      "description": {"type": "string", "description": "skill 描述"}
    },
    "required": ["name"]
  },
  "steps": [
    {
      "name": "update",
      "tool_name": "update_skill",
      "arguments_from_input": ["name", "description"]
    },
    {
      "name": "preview",
      "tool_name": "read_skill",
      "arguments_from_input": ["name"]
    }
  ],
  "finalizer": "skill_file_preview"
}
```

## Current Constraints

- Steps support legacy `arguments_from_input` and schema v2 `arguments`, but do not yet support conditional branches or loops.
- Finalizers currently use a fixed named registry (`skill_file_preview`, `last_step_text`).
- External code execution is not supported.
- Tool definitions directory exists but loader support for external tools is intentionally not enabled yet.
- User-defined workflows can now be managed through runtime tools:
  - `list_workflows`
  - `read_workflow`
  - `create_workflow`
  - `update_workflow`
  - `delete_workflow`
- Natural-language helpers now target the same schema:
  - `draft_workflow_from_request`
  - `create_workflow_from_request`
  - `update_workflow_from_request`
- Workflow definitions are still declarative JSON only; arbitrary Python handlers are not part of this phase.

## Why This Shape

This spec is intentionally narrow so workflows can:

1. Be validated safely.
2. Compile into normal `ToolSpec` entries.
3. Inherit provider projection, `/tools` discovery, and confirmation policy automatically.
4. Serve as the future substrate for user-defined workflows.
