# Runtime Architecture

## Main flow

The runtime path for scene operations is:

```text
MCP client
    -> MCP tool function
    -> SceneService
    -> SceneAPI
    -> Adapter
    -> Gaussian Splatting engine
```

In the current repository, the last step is provided by the deterministic `mock` adapter.

## Text diagram

```text
src/lichtfeld_mcp/server.py
    registers MCP tools

tools/*.py
    thin MCP entrypoints
    no engine logic

SceneService
    business facade used by tools

core.SceneAPI
    orchestration, validation, request objects, normalization

adapters.base.LichtfeldAdapter
    engine contract

adapters.mock.MockLichtfeldAdapter
    current working backend
```

## Layer roles

### MCP tools

The tool modules translate MCP calls into typed Python calls and return serialized results.

They should remain thin and operationally boring.

### SceneService

`SceneService` is the application-facing service layer used by MCP tools.

It exists to give tools a stable business facade and to prevent them from coupling directly to `SceneAPI` internals or adapter details.

### SceneAPI

`SceneAPI` is the core orchestration layer for scene operations.

It is responsible for:

- validating inputs;
- normalizing primitive values;
- building request objects;
- enforcing scene-level rules before adapter calls.

### Adapter

The adapter is the bridge to a concrete backend.

It may call:

- a local executable;
- a Python SDK;
- a socket service;
- an HTTP API;
- or a deterministic mock implementation.

## Architecture rules

- MCP tools must never call an adapter directly.
- `SceneService` is the business facade for tools.
- `SceneAPI` defines and enforces the scene interaction contract.
- Adapters implement real or mock backends behind that contract.

## Current status

- `mock` is functional and covered by tests.
- a real Lichtfeld adapter is planned but not implemented yet.
