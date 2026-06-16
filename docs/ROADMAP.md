# Roadmap

## V1 - MCP skeleton and deterministic mock
- MCP stdio server
- Basic scene tools
- Selection and crop primitives
- Export and optimization primitives
- Deterministic mock adapter

## V2 - Lichtfeld integration layer
- Replace mock adapter by CLI adapter or Python SDK adapter
- Add project manifest reader
- Add real import/export validation
- Add logging and operation telemetry

## V3 - Gaussian-specific editing
- Real splat selection by bounding box
- Real color/opacity/density filters
- Real crop/delete operations
- Undo/redo bridge with Lichtfeld history

## V4 - Semantic edition
- Render multi-view thumbnails
- Detect objects in source images or rendered views
- Project 2D masks to splat IDs
- Expose tools such as `select_object("person")` and `remove_object("car")`

## V5 - Production assistant
- Batch processing
- Profile-based optimization: Quest 3, Web, Unity, Unreal, Vision Pro
- Scene quality report
- Dataset inspection
