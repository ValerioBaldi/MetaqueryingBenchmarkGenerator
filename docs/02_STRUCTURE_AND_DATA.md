# 02 — Directory structure and data dictionary

[Back to README](../README.md)

## Directories

| Path | Purpose | Recommended handling |
|---|---|---|
| `data/src/taxonomiesNew/` | Original taxonomy TSVs | Preserve and version |
| `data/src/*.tsv` | Animal and relationship sources, including `AnimalHierarchy.tsv` | Preserve and version |
| `data/processed/` | Cleaned/normalized TSV outputs | Regenerable from source and code |
| `generators/` | ETL pipeline, OWL builder, parametric GUI | Version |
| `ontology/` | Full OWL used as the baseline for subsets | Version or retain with hash |
| `generated_benchmarks/` | Generated OWL suites and metadata | Retain for experiment reproducibility |
| `queries/` | Numbered SPARQL queries | Version together with experiments |
| `archive/` | Previous suites and source datasets | Do not delete without documented migration |
| `queries.txt` | Historical notes/queries | Do not assume equivalence with `queries/` |

## Input to `taxonomy.py`

`data/src/taxonomiesNew/` contains taxonomy TSVs with the following columns:

| Column | Meaning |
|---|---|
| `taxon` | Taxon identifier |
| `parent` | Parent taxon identifier, if available |
| `rank` | Taxonomic rank identifier/IRI, if available |
| `name` | Human-readable taxon label, if available |

The script concatenates input files sorted by filename, drops records without a `taxon`, removes identical duplicates, sorts by `taxon,parent,rank,name`, and writes `data/processed/taxonomy_normalized.tsv`. The included output has **620 data rows**, using these four columns.

## Input to `filterIndividuals_mapped.py`

| File | Required columns | Output |
|---|---|---|
| `data/src/animalIndividuals.tsv` | `x`, `class` | `data/processed/animalIndividuals_filtered.tsv` |
| `data/src/AnimalsNew.tsv` | `class`, `taxon`, `animal` | `data/processed/animalsNew_filtered.tsv` |
| `data/processed/taxonomy_normalized.tsv` | `taxon` | Used to validate and map classes |

The class in `animalIndividuals.tsv` may already be a taxon or may map to a taxon through the `class → taxon` mapping derived from `AnimalsNew.tsv`. This mapping can be one-to-many; the output retains distinct resulting `(x, class)` pairs. The second output retains only animal identifiers matching Wikidata `Q...` items and taxa present in the normalized taxonomy.

## Additional inputs to `translateToOntologyComplete.py`

| File | Columns required by code | Use |
|---|---|---|
| `data/src/predator_relations.tsv` | `predator`, `prey`, `role` | `predatorOf` assertions and subroles |
| `data/src/coexists_relations.tsv` | `taxon1`, `taxon2` | `coexistsWith` assertions |
| `data/src/disjoint_classes.tsv` | `class1`, `class2` | `owl:disjointWith` assertions |
| `data/processed/animalIndividuals_filtered.tsv` | `x`, `class` | Individual type assertions |
| `data/processed/animalsNew_filtered.tsv` | `class`, `taxon`, `animal` | `animal rdf:type taxon` assertions |

The sources include `http://www.wikidata.org/entity/...` identifiers, `wd:` prefixes, and local identifiers. The `iri()` function in the OWL builder preserves HTTP(S) URLs, expands `wd:`, and places other values in the `http://example.org/taxonomy/` namespace. Changing this rule changes the dataset IRIs.

## Included processed files

| File | Columns | Data rows in this release |
|---|---|---:|
| `taxonomy_normalized.tsv` | `taxon,parent,rank,name` | 620 |
| `animalIndividuals_filtered.tsv` | `x,class` | 29,066 |
| `animalsNew_filtered.tsv` | `class,taxon,animal` | 3,473 |

The number of **data rows** is not the number of **distinct individuals**: a resource may appear in multiple rows or in both files. Duplicate `(individual, taxon)` pairs are removed during OWL construction.