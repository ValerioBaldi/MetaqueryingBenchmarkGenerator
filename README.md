# Parametric OWL Benchmark Generator

**Documentation for the `benchmark/` project — October 30, 2026**  
Language: English · Implementation: Python + pandas + RDFLib + Tkinter · Ontology format: OWL serialized as RDF/XML.

## Purpose

This project builds a taxonomic ontology from TSV files and generates **controlled subsets of the ontology** for scalability and metaquery-answering experiments. The dataset contains taxonomic classes that are also used as individuals (*class metamodeling*), assertions about ordinary animals, ecological/taxonomic relationships, and property axioms.

The project generates **data**. It does **not** itself perform OWL-to-Datalog rewriting, materialize Datalog programs, or benchmark i-DLV or Soufflé execution times. The SPARQL queries in `queries/` are intended for a separate query-processing pipeline.

## Quick start

**Python 3.10 or later** is recommended, with **pandas** and **rdflib** installed. The graphical application also requires **Tkinter**.

```powershell
py -m pip install pandas rdflib
py generators\parametric_benchmark_generator_Final.py
```

The interface can analyze the source ontology, select presets and semantic filters, generate a benchmark, and export reports. The default ontology is `ontology/animal_taxonomy_ontology_complete.owl`.

To **rebuild the ontology from its TSV sources**:

```powershell
py generators\taxonomy.py
py generators\filterIndividuals_mapped.py
py generators\translateToOntologyComplete.py
```

> **Warning:** the last command overwrites `ontology/animal_taxonomy_ontology_complete.owl` if it already exists. Back it up before rebuilding an ontology used in previous experiments.

On Linux, use `python3` instead of `py`, and install `python3-tk` through the system package manager if Tkinter is unavailable.

## Main directory structure

```text
benchmark/
├── README.md                     # Main documentation
├── docs/                         # Detailed documentation
├── data/
│   ├── src/                      # Source TSVs; taxonomiesNew/; auxiliary AnimalHierarchy.tsv
│   └── processed/                # Cleaned and normalized TSVs
├── generators/
│   ├── taxonomy.py
│   ├── filterIndividuals_mapped.py
│   ├── translateToOntologyComplete.py
│   └── parametric_benchmark_generator_Final.py
├── ontology/
│   └── animal_taxonomy_ontology_complete.owl
├── generated_benchmarks/         # Current benchmark suites and historical metadata
│   ├── ABox/
│   ├── ABoxNoDisj/
│   ├── ABoxNoProperties/
│   ├── TBox/
│   └── TBoxNoABox/
├── queries/                      # query1.sparql ... query18.sparql
├── queries.txt                   # Historical query notes
└── archive/                      # Older data and suites; not necessarily equivalent
```

## Included full ontology: baseline statistics

These values are calculated from the included OWL file **without inference**:

| Metric | Value |
|---|---:|
| RDF triples | 36,002 |
| Explicitly declared OWL classes | 632 |
| Typed ordinary individuals (generator definition) | 29,989 |
| Ordinary-individual type assertions | 32,297 |
| `rdf:type` assertions between classes (metamodeling) | 1,084 |
| Classes used as individuals | 630 |
| Identified metaclasses | 48 |
| Object properties | 11 |
| Explicit role assertions | 722 |

See [Reports and reproducibility](docs/06_REPORTS_AND_REPRODUCIBILITY.md) for the definition of source and output statistics.

## Documentation contents

1. [Installation and getting started](docs/01_GETTING_STARTED.md)
2. [Directory structure and data dictionary](docs/02_STRUCTURE_AND_DATA.md)
3. [Ontology construction and semantic model](docs/03_ONTOLOGY_AND_SEMANTICS.md)
4. [Parametric generator: GUI and algorithms](docs/04_PARAMETRIC_GENERATOR.md)
5. [Benchmark and query catalog](docs/05_BENCHMARK_AND_QUERY_CATALOG.md)
6. [Output formats, reports, and reproducibility](docs/06_REPORTS_AND_REPRODUCIBILITY.md)
7. [Building and distributing the Windows `.exe`](docs/07_WINDOWS_EXE.md)
8. [Limitations, checks, and future work](docs/08_LIMITATIONS_AND_FUTURE_WORK.md)
9. [Python component reference](docs/09_PYTHON_API_REFERENCE.md)
10. [Glossary](docs/10_GLOSSARY.md)
11. [Inventory and SHA-256 hashes](docs/11_INVENTORY_AND_HASHES.md)

## Three important clarifications

- **A1–A5** use **10/25/50/75/100% sampling per primary stratum**, rounded up with at least one representative per stratum. The overall individual counts are therefore not necessarily exactly those percentages of the full dataset.
- **T1–T4** GUI presets generally sample 25% of eligible ordinary individuals for the selected classes. Historical `TBoxNoABox/` configurations instead use `classes_only`, with no ordinary individuals. These two series must not be conflated.
- Existing `*_config.json` files may still contain **old Windows paths and OWL names that do not match the actual files**. They are historical metadata: verify the matching OWL before automated processing, and do not silently rewrite their provenance.

## Licensing, provenance, and distribution

The source data contain Wikidata identifiers and triples assembled from local tables. Such identifiers are not independent validation of the biological claims. **No software LICENSE file was found in the analyzed archive**. Before public release, select an appropriate code license and check the provenance/licensing of included data. Python package versions are not pinned in a lockfile; record the precise versions used for comparable experiments.
