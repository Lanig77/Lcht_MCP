# Lichtfeld MCP Gaussian Editor

Prototype open source d'un serveur **Model Context Protocol** pour piloter un éditeur Gaussian Splatting de type **Lichtfeld Studio** depuis ChatGPT, Claude Desktop, Cursor ou tout autre client MCP.

Cette V1 est volontairement structurée comme un vrai repo produit : serveur MCP, outils typés, adaptateur remplaçable, tests, documentation et exemples Windows.

## Objectif

Permettre à un assistant IA de traduire des intentions utilisateur en opérations d'édition Gaussian Splatting :

- ouvrir un projet ;
- inspecter une scène ;
- sélectionner une zone ;
- supprimer une sélection ;
- cropper par boîte ou hauteur ;
- optimiser pour Quest 3, Web, Unity, Unreal ;
- exporter en PLY/SPZ/SPLAT ;
- mesurer une distance ;
- annuler une opération.

## Important

Cette version utilise un **adaptateur simulé** (`mock`). Elle ne modifie pas encore de vrais fichiers Lichtfeld. Le but est de valider l'architecture MCP et les contrats d'API avant de brancher une vraie API Lichtfeld Studio.

## Installation Windows PowerShell

Depuis le dossier du projet :

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

## Test rapide sans client MCP

```powershell
python -m lichtfeld_mcp.dev_cli
```

Tu dois obtenir une sortie JSON avec ouverture de projet, statistiques, sélection, suppression, optimisation Quest 3 et export simulé.

## Lancer le serveur MCP

```powershell
python -m lichtfeld_mcp.server
```

Le serveur utilise le transport `stdio`, donc il attend normalement d'être lancé par un client MCP. Dans un terminal, il peut sembler ne rien afficher : c'est normal.

## Commande installée

Après installation :

```powershell
lichtfeld-mcp
```

Si cette commande n'est pas reconnue, utilise :

```powershell
python -m lichtfeld_mcp.server
```

## Tests

```powershell
python -m pytest
```

## Configuration Claude Desktop exemple

Voir :

```text
examples/claude_desktop_config.json
```

## Architecture

```text
src/lichtfeld_mcp/
├── server.py                 # Entrée serveur MCP
├── app_state.py              # Factory d'adaptateur
├── adapters/
│   ├── base.py               # Contrat d'API attendu
│   └── mock.py               # Simulateur local
├── schemas/
│   └── common.py             # Modèles Pydantic
└── tools/
    ├── scene.py              # Open/save/stats/history
    ├── selection.py          # Sélections
    ├── edit.py               # Crop/edit
    ├── optimize.py           # Optimisation cible
    ├── export.py             # Export
    └── measure.py            # Mesures
```

## Outils MCP exposés

- `open_project(path)`
- `save_project()`
- `close_project()`
- `get_scene_stats()`
- `select_by_box(...)`
- `select_by_height(...)`
- `select_by_color(...)`
- `delete_selection()`
- `crop_by_box(...)`
- `crop_by_height(...)`
- `optimize_for_target(target, max_splats=None)`
- `export_scene(output_path, fmt="ply", target=None)`
- `measure_distance(...)`
- `undo()`
- `list_history()`

## Prochaine étape : brancher Lichtfeld Studio

Le fichier important est :

```text
src/lichtfeld_mcp/adapters/base.py
```

Il définit le contrat minimal que Lichtfeld Studio devrait exposer. Pour passer du mock à un vrai logiciel, il faut créer un nouvel adaptateur, par exemple :

```text
src/lichtfeld_mcp/adapters/lichtfeld_cli.py
src/lichtfeld_mcp/adapters/lichtfeld_sdk.py
src/lichtfeld_mcp/adapters/lichtfeld_socket.py
```

Puis modifier `app_state.py` pour sélectionner cet adaptateur via :

```powershell
$env:LICHTFELD_ADAPTER="cli"
```

## Philosophie

Le LLM ne doit jamais manipuler directement les splats. Il appelle des outils typés. Lichtfeld Studio reste responsable du moteur 3D, des fichiers, du rendu, de l'historique et de l'optimisation.
