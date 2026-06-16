# Adapters

## Purpose

Adapters are the backend integration layer for `Lcht_MCP`.

They implement the engine-facing behavior behind the abstract contract defined in `adapters/base.py`.

## Contract

An adapter must provide the scene operations expected by the runtime, including:

- project lifecycle;
- scene statistics;
- selection and crop operations;
- optimization;
- export;
- measurement;
- undo/history.

`SceneAPI` and `SceneService` depend on this contract, not on a concrete engine implementation.

## Current implementation

The repository currently ships one adapter:

- `MockLichtfeldAdapter`

This adapter is:

- deterministic;
- in-memory;
- test-friendly;
- useful for validating the architecture and API contracts.

It is not a real Gaussian Splatting engine backend.

## Planned real backends

The intended next step is a real Lichtfeld backend, for example through:

- a CLI bridge;
- a Python SDK;
- a socket protocol;
- or another local integration mechanism.

Those adapters should fit under the same contract without requiring MCP tool rewrites.

## Architecture rules

- Tools must never talk to adapters directly.
- `SceneService` is the entry facade for tool-level operations.
- `SceneAPI` prepares validated scene operations before adapter calls.
- Adapters contain backend-specific implementation logic only.

## Current status

- `mock` is functional and used by tests.
- a real Lichtfeld adapter is not connected yet.
- the adapter boundary is already in place, which is the main architectural milestone at this stage.
