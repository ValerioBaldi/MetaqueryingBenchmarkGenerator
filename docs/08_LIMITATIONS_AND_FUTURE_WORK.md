# 08 — Limitations, validation checks, and future extensions

[Back to README](../README.md)

## Current limitations confirmed in the code

1. **Metaproperties are not yet a separate entity category.** `get_ordinary_individual_types()` only excludes OWL classes from ordinary-individual candidates. An object property that is itself an instance of an OWL class may therefore be sampled as an ordinary individual. Dedicated classification and graph-filtering rules are needed to handle classes, properties, and ordinary individuals consistently.
2. **Role filters depend on known IRI families.** The code explicitly recognizes local predation, taxonomy, and coexistence properties. New properties fall under `other_roles` until classification is extended.
3. **No inference during generation.** Reports count explicit RDF triples, which can differ considerably from post-materialization relation sizes.
4. **Deterministic algorithms are not always optimal.** The `abox_aware` greedy heuristic in `fixed` mode cannot solve all cardinality/class-selection combinations exactly and may fail.
5. **Dependency cycles may cause generation failure.** Topological ordering raises an error when dependency graphs contain cycles; it does not automatically collapse strongly connected components.
6. **Memory and scalability constraints.** RDFLib loads the entire source ontology into a `Graph`. Very large inputs may require considerable RAM; there is no streaming implementation.
7. **Phase-based progress reporting.** The progress bar is not an elapsed/remaining-time estimate, and does not show per-triple progress within long phases.
8. **Full semantic reports are only generated for new runs.** Existing historical suites are not updated automatically.
9. **No automated tests are shipped with the project.** The distributed folder does not contain a `pytest` suite or CI configuration, although checks were carried out while the project was updated.

## Checks recommended for each new version

| Check | Expected criterion |
|---|---|
| TSV integrity | Required columns exist; unexpected blank records are not introduced |
| Full ontology | RDF graph loads correctly and counts can be explained |
| A1–A5 sampling | Same source and seed produce nested individual sets by stratum |
| Dependency closure | Every selected class includes required active prerequisites |
| `classes_only` mode | `ordinary_individuals == 0`; preserve metamodeling if enabled |
| Disabled role families | No assertions for excluded properties remain in OWL |
| Reports | Reported explicit counts agree with generated graph |
| Overwrite protection | Existing files remain protected when overwrite is disabled |
| Cross-platform behavior | GUI and `.exe` work on the intended destination OS |
| Reasoning compatibility | Queries and answer sets are validated using the relevant external translator/engine |

## Proposed future work: new object properties and metaproperties

This section is a **proposal**, not a description of features already implemented.

### Additional ordinary roles

Introduce relationships such as `interactsWith`, `inhabits`, and `hasHabitat`, with controlled role hierarchies and configurable assertion density. Keep a clear separation between source-derived assertions and synthetic facts, and record the generation seed and density parameters.

### Property metamodeling

A dedicated **property-as-individual** category would require at least:

1. Detect declared object properties that also have `rdf:type` assertions to a metaclass.
2. Exclude them from ordinary ABox individual counts and sampling.
3. Preserve/filter triples of the form `property rdf:type MetaPropertyClass` consistently.
4. Support **metaproperties** relating properties to other resources, such as `hasInteractionContext`.
5. Report additional measurements (`properties_used_as_individuals`, `metaproperty_assertions`) and expose controlled experiment-series generation.
6. Check downstream SPARQL-to-Datalog support for **variable predicates** such as `?x ?p ?y`, including the intended MSER interpretation.

### Possible experimental series

- **R**: scalability in the number of ordinary role assertions.
- **H**: role-hierarchy depth and inclusion density.
- **M**: number of properties also used as individuals.
- **MP**: number of metaproperty assertions.

Change one main parameter at a time to avoid confounding reasoning cost with simultaneous growth in other dataset dimensions.
