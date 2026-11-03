# 09 — Python component reference

[Back to README](../README.md)

This page describes functions **actually present in the delivered version**. It does not claim that they form a stable public API. Most scripts are designed as applications, not libraries with formally versioned interfaces.

## `taxonomy.py`

A top-level script without a dedicated `main()` function. It reads `data/src/taxonomiesNew/` TSVs, concatenates, deduplicates, and sorts rows, and writes `data/processed/taxonomy_normalized.tsv`. Its read/write operations run **on import**, so it should not be imported merely to reuse helper functions.

## `filterIndividuals_mapped.py`

| Function | Responsibility |
|---|---|
| `read_tsv(path, required_columns)` | Read a TSV and validate required columns |
| `non_empty_values(dataframe, column)` | Collect distinct nonempty values |
| `is_wikidata_item(value)` | Validate Wikidata `Q...` item URI |
| `build_class_to_taxon_mapping(...)` | Build `class → taxon` associations |
| `process_individuals(...)` | Generate `animalIndividuals_filtered.tsv` |
| `process_animals_new(...)` | Generate `animalsNew_filtered.tsv` |
| `main()` | Orchestrate preprocessing |

Input and output filenames are defined by globals based on `PROJECT_ROOT`; update them if the source layout changes.

## `translateToOntologyComplete.py`

This is mainly a **top-level** script: it creates `g = Graph()` and builds the ontology as the module is imported. Relevant local functions:

- `iri(value)`: handle HTTP(S) IRIs, `wd:` prefixes, and local identifiers.
- `read_tsv(path, required_columns)`: validate TSV structure.
- `is_wikidata_item(value)`: check Wikidata identifiers in the secondary source.

When maintaining this script, pay attention to code blocks that directly add triples to `g`. There is currently no isolated `OntologyBuilder` object or argument-based command-line interface.

## `parametric_benchmark_generator_Final.py`

### Entity identification and selection

| Function | Purpose |
|---|---|
| `get_classes(graph)` | Return explicitly declared `owl:Class` entities |
| `get_object_properties(graph)` | Return declared object properties |
| `get_ordinary_individual_types(graph, classes)` | Return direct ordinary-individual types under current rule |
| `build_class_dependencies(...)` | Build subclass and metamodeling dependencies |
| `dependency_safe_order(...)` | Deterministic topological ordering |
| `dependency_closure(...)` | Compute dependency closure |
| `select_classes_abox_aware(...)` | Individual-coverage greedy selection |
| `build_subclass_parents(...)` | Direct subclass-parent mapping |
| `longest_subclass_chain(...)` | Identify a deepest hierarchy chain |
| `select_classes_tbox_oriented(...)` | TBox-prioritized class selection |
| `select_individuals(...)` | Select a fixed number of individuals |
| `select_individuals_by_percentage(...)` | Per-primary-stratum sampling |

### Graph filtering and statistics

| Function | Purpose |
|---|---|
| `property_family_enabled(prop, options)` | Determine whether a role family is enabled |
| `filter_graph(...)` | Construct the output subgraph |
| `benchmark_stats(...)` | Basic output statistics |
| `role_family_name(prop)` | Classify as predation/taxonomic/coexistence/other |
| `ontology_semantic_profile(graph)` | Create a complete explicit semantic profile, JSON-serializable |
| `format_ontology_overview(profile)` | Format source statistics for GUI display |
| `make_semantic_report(...)` | Produce a readable source/configuration/output report |

### `BenchmarkGUI` class

- `__init__()` creates widgets, analysis cache, GUI state, and queue polling.
- `_read_full_sizes()` retrieves class and ordinary-individual counts from the full graph.
- `_apply_abox_preset()` and `_apply_tbox_preset()` configure the respective presets.
- `_analyze_dataset()` and `_analyze_worker()` handle source analysis.
- `_snapshot_generation_settings()` reads GUI variables on the main thread.
- `_start_generation()` and `_worker()` manage generation without blocking the GUI.
- `_generate(settings)` performs the central workflow: reading, selection, filtering, profiles, OWL serialization, and report writing.
- `_set_phase()` and `_drain_log_queue()` connect background work to the progress display.
- `_finished()` updates the GUI when a run completes.

Python threads keep the UI responsive; they do **not** implement distributed execution or a job scheduler. Avoid invoking private GUI methods from unrelated threads without accounting for Tkinter's threading rules.

## Constants to update when datasets change

- `ABOX_PRESETS`, `TBOX_PRESETS`, `DEFAULT_TBOX_INDIVIDUAL_PERCENTAGE`.
- `PREDATION_PROPERTIES`, `TAXONOMIC_PROPERTIES`, `COEXISTS_PROPERTIES`, plus `property_family_enabled` for newly introduced roles.
- `SOURCE_DIR`, `PROCESSED_DIR`, `ONTOLOGY_DIR`, `BENCHMARKS_DIR` if the project directory layout changes.
- Default input/output filenames and directories in `BenchmarkGUI.__init__()`.

**Import behavior:** the parametric generator can be imported without opening its GUI because `BenchmarkGUI` is instantiated only from `main()`. The other scripts are not all import-safe: some perform top-level work immediately.
