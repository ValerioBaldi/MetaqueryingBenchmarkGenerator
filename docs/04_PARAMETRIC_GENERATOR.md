# 04 — Parametric generator: interface, options, and algorithms

[Back to README](../README.md)

## Main component

`generators/parametric_benchmark_generator_Final.py` is a Tkinter desktop application. It reads a complete RDF/OWL ontology through RDFLib and creates a parameterized OWL subgraph. The GUI does **not** preprocess the TSV files; its input must already be a **complete OWL ontology**.

### GUI panels

| Panel | Contents |
|---|---|
| Input / output | Input OWL path, output folder, benchmark name, analysis action |
| Source ontology statistics | Detailed explicit-source-ontology statistics, without inference |
| Benchmark size | Number of classes, class-selection strategy, seed |
| Individual sampling | Percentage, fixed count, all eligible individuals, or classes only |
| Benchmark presets | A1–A5 and T1–T4; restore all semantic features |
| Semantic features | Inclusions, metamodeling, inverses, disjointness, reflexive/irreflexive properties |
| Role families | Predation, taxonomy, coexistence, or other role families |
| Generation progress | Phase-based progress bar |
| Log | Generation messages and statistics |

## Presets

| Preset | Class count | Individual sampling | Strategy |
|---|---:|---|---|
| A1 | All | 10% per stratum | GUI sets `abox_aware`; percentage mode uses dependency-safe ordering |
| A2 | All | 25% per stratum | As A1 |
| A3 | All | 50% per stratum | As A1 |
| A4 | All | 75% per stratum | As A1 |
| A5 | All | 100% per stratum | As A1 |
| T1 | 150 | 25% per eligible stratum | `tbox_oriented` |
| T2 | 300 | 25% per eligible stratum | `tbox_oriented` |
| T3 | 450 | 25% per eligible stratum | `tbox_oriented` |
| T4 | All | 25% per eligible stratum | `tbox_oriented` |

**All presets reset the seed to `42` and enable all optional semantic features and role families.** T4 may differ from A5 because it samples 25%, rather than 100%, of eligible ordinary individuals. A preset button configures one generation; it does not produce an entire suite automatically.

### Class-selection strategies

- **`abox_aware` with `fixed` sampling:** a greedy coverage heuristic aims to select exactly N dependency-closed classes, favoring additions that make many individuals eligible. It is not an exact optimization method and may fail even when a solution exists.
- **`abox_aware` with `percentage`, `all`, or `classes_only`:** selects a prefix of a deterministic topological order, preserving enabled class dependencies.
- **`tbox_oriented`:** retains a deepest subclass chain where feasible and prioritizes a dependency-closed core. The final set is the prefix of a specially prioritized topological ordering.

Dependencies come from `rdfs:subClassOf` (child → parent), and, when metamodeling is enabled, class-to-metaclass `rdf:type` relationships (class → metaclass). Dependency cycles raise an error rather than silently producing a subset missing prerequisites.

### Individual-sampling modes

- **`percentage`:** choose a percentage in `(0, 100]` for each primary stratum. An individual is assigned to its **rarest selected direct class** (ties broken by IRI). In every stratum, the generator selects the first `max(1, ceil(p * size / 100))` members from a deterministic, SHA-256/seed-based pseudorandom order.
- **`fixed`:** select exactly N individuals where possible. The selection initially includes stratum representatives (as capacity allows), followed by deterministic weighted sampling that favors rare strata (`1/sqrt(size)`).
- **`all`:** include every eligible individual for the selected classes; equivalent to 100% of every stratum.
- **`classes_only`:** exclude ordinary individuals while retaining class metamodeling assertions if enabled.

The nesting property `A1 ⊆ A2 ⊆ ... ⊆ A5` applies to selected individuals **only when the ontology, class set, seed, and filters remain fixed**. It does not apply across different seeds/class sets, nor necessarily to the TBox series as a whole when eligibility changes.

## GUI semantic filters

| Option | Controlled predicates/triples |
|---|---|
| `include_subclass` | `rdfs:subClassOf` |
| `include_metamodeling` | `rdf:type` with subject and object both selected classes |
| `include_subproperty` | `rdfs:subPropertyOf` |
| `include_inverse` | `owl:inverseOf` |
| `include_class_disjointness` | `owl:disjointWith` |
| `include_role_disjointness` | `owl:propertyDisjointWith` |
| `include_reflexive` | `rdf:type owl:ReflexiveProperty` |
| `include_irreflexive` | `rdf:type owl:IrreflexiveProperty` |
| `include_predation_roles` | Eight predation and inverse-predation object properties |
| `include_taxonomic_roles` | Two parent/child taxonomy properties |
| `include_coexists_role` | `coexistsWith` |
| `include_other_roles` | Object properties not classified in the above families |

Domain and range triples are preserved **when the property is enabled and the referenced class is part of the selected set**. There is no separate domain/range checkbox. Enabling an option does not guarantee that any matching triple exists in the output; the semantic reports distinguish configuration from actual content.

## How `filter_graph()` works

The function filters class declarations; property declarations and axioms; types of ordinary individuals; metamodeling assertions between classes; inclusions; disjointness; domain/range statements; labels; and role assertions. It keeps a role assertion when the family is enabled and the relevant selectable endpoints have not been excluded.

**Important limitation before adding metaproperties:** the current ordinary-individual classification includes any subject typed with an OWL class unless that subject is itself an OWL class. Therefore, a property used as an individual may be incorrectly sampled as an ordinary individual. The implementation must be extended before using this category of data.

## Source preview and progress bar

**Analyze dataset** calculates source statistics in a separate thread. A cache based on the path, file size, and modification timestamp avoids unnecessary recomputation if the file is unchanged. Generation likewise uses a worker thread and a queue to update the GUI.

The progress bar displays **discrete phases**, at 0/5/18/27/43/57/60/74/78/83/90/92/100%. It is **not** a remaining-time estimate, a percentage of triples examined, or an indicator of CPU use. The bar may appear stationary during a long-running phase.

## Output files

Each generation produces five files sharing one base name:

```text
<name>.owl
<name>_config.json
<name>_stats.tsv
<name>_semantic_report.json
<name>_semantic_report.txt
```

See [06 — Reports and reproducibility](06_REPORTS_AND_REPRODUCIBILITY.md) for details.
