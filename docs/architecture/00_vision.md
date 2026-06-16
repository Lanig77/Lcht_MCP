# Architecture Vision

## Goal

`Lcht_MCP` is a Model Context Protocol framework for controlling Gaussian Splatting engines from an MCP client such as ChatGPT, Claude Desktop, or another compatible assistant.

The long-term goal is not to build a Gaussian editor inside the LLM. The goal is to expose a stable, typed control layer so an assistant can drive an external engine safely.

## Product direction

The project is designed as a backend-agnostic control framework:

- MCP is the user-facing protocol surface.
- `Lichtfeld` is the intended first real backend.
- Additional engines can be added later through adapters.

## Current state

Today, the repository is in an architectural validation phase:

- the MCP server is functional;
- the runtime flow from tools to adapter is functional;
- the `mock` adapter is the only working backend;
- a real Lichtfeld backend is not connected yet.

## Design intent

The architecture separates responsibilities so that each layer stays narrow:

- tools expose MCP-compatible functions;
- services provide a business-facing facade;
- `SceneAPI` centralizes scene orchestration and validation;
- adapters isolate engine-specific implementation details.

This separation is what allows the project to evolve from a deterministic mock backend to a real Gaussian Splatting engine without rewriting the MCP surface.
