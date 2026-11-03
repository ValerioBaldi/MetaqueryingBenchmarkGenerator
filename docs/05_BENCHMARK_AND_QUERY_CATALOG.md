# 05 — Existing benchmark suites and query catalog

[Back to README](../README.md)

## Five benchmark families

`generated_benchmarks/` currently contains **23 OWL files** and associated metadata. These files were generated before the addition of semantic reports and some path corrections.

| Family | Available sizes | Documented meaning |
|---|---|---|
| `ABox` | A1–A5 | All classes; 10/25/50/75/100% individuals per stratum; semantic features enabled |
| `ABoxNoDisj` | A1–A5 | As ABox, but class and role disjointness disabled |
| `ABoxNoProperties` | A1–A5 | As ABox, but object-property families disabled; class axioms and metamodeling remain |
| `TBox` | T1–T4 | 150/300/450/all classes, with 25% sampling per eligible individual stratum |
| `TBoxNoABox` | T1–T4 | 150/300/450/all classes, `classes_only` mode: no ordinary individuals, class metamodeling retained |

**Terminology:** `ABoxNoProperties` does **not** mean a dataset without any predicates or type assertions. It refers to disabled **object-property families**, following the feature configurations in the historical JSON files. `TBoxNoABox` is not equivalent to the T1–T4 presets that the current GUI normally loads.

## Saved dataset counts

These figures come from the associated `*_stats.tsv` files in the supplied archive. They are **saved historical counts**, not newly measured runtime-performance results.

| Series / test | Classes | Ordinary individuals | RDF triples |
|---|---:|---:|---:|
| ABox A1 | 632 | 3,070 | 7,053 |
| ABox A2 | 632 | 7,551 | 11,859 |
| ABox A3 | 632 | 15,031 | 19,904 |
| ABox A4 | 632 | 22,534 | 27,991 |
| ABox A5 | 632 | 29,989 | 36,002 |
| NoDisj A5 | 632 | 29,989 | 35,951 |
| NoProperties A5 | 632 | 29,989 | 35,187 |
| TBox T1 | 150 | 323 | 1,084 |
| TBox T2 | 300 | 681 | 2,343 |
| TBox T3 | 450 | 7,140 | 9,924 |
| TBox T4 | 632 | 7,551 | 11,859 |
| TBoxNoABox T1 | 150 | 0 | 539 |
| TBoxNoABox T2 | 300 | 0 | 1,227 |
| TBoxNoABox T3 | 450 | 0 | 1,974 |
| TBoxNoABox T4 | 632 | 0 | 2,890 |

Ordinary-individual counts in the TBox series are not constant: they depend on selected classes and the eligible individuals typed with them. T4 means the full **class** count, not the full ABox.

## SPARQL query catalog

`queries/` contains **18 files**, named `query1.sparql` through `query18.sparql`.

| Query | Main pattern |
|---|---|
| Q1–Q4 | `rdf:type` assertions for fixed Wikidata classes |
| Q5 | `landPredatorOf` |
| Q6 | `predatorOf` |
| Q7 | `preyOf` (relevant to inverse-role axioms) |
| Q8 | Join involving `landPredatorOf` and `preyOf` |
| Q9 | Individuals that are both `owl:Class` and instances of `ex:Taxon` |
| Q10 | Classes that are instances of a fixed taxonomic class |
| Q11 | Join between an individual's `rdf:type` and classification of its type as `ex:Taxon` |
| Q12 | Pairs related through `owl:disjointWith` |
| Q13 | Reflexive pattern `?x ex:coexistsWith ?x` |
| Q14 | `owl:differentFrom` assertions |
| Q15 | Predation join with types of predator and prey |
| Q16 | Three-step chain of predation assertions |
| Q17 | Multi-role join (predation, aquatic predation, inverse `preyOf`) and types |
| Q18 | Predators with a shared type, common prey, and `owl:differentFrom` |

These descriptions reflect the files **in this project folder**. Their numbering and content may differ from later versions used in the thesis, especially since Q15–Q18 were revised during the experimental work.

### Important query-execution caveats

- The provided SPARQL files use the prefixes `rdf:`, `owl:`, `wd:`, and `ex:`, but **do not contain `PREFIX` declarations**. A generic SPARQL engine may require those declarations; the relevant translator must supply a prefix mapping.
- The parametric generator **does not execute these queries or translate them to Datalog**, and this folder does not include i-DLV/Soufflé runner scripts.
- A query using `owl:differentFrom` does not imply that the current ontology contains explicit assertions of that predicate. Check the dataset and entailment regime before assuming an expected answer count.
- Empty answers can arise from configuration, dataset size, the semantic profile, translation behavior, or missing facts. Do not change the input merely to force nonempty results without documenting the change.

## Preserve an experimental run

For each run, retain the input OWL hash, code/revision, seed, preset or custom parameters, all five generator outputs, downstream engine versions, exact query files, execution mode, repetition count, and timing/memory logs. Avoid reusing an output directory if overwriting would destroy earlier provenance.
