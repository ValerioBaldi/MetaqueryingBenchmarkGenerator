# 11 — Technical inventory and SHA-256 hashes of core files

[Back to README](../README.md)

## Snapshot and provenance

This inventory was updated on **2026-11-03**, using the exact file contents
of the supplied `benchmark(4).zip` plus the new `requirements.txt` and `LICENSE`.
Only the inventory and a few README references were changed; generator code,
source data, generated benchmarks, and ontology contents were left unchanged.

The snapshot contains **302 files** (excluding directory entries), including
historical archives, PyInstaller build intermediates, and a Windows executable.
The source ZIP contained 300 files; the two new root-level files account for
the difference. The counts below describe this snapshot, **not a cleaned
GitHub release**.

## Inventory by top-level directory

| Location | Files |
|---|---:|
| `generators` | 4 |
| `data` | 83 |
| `ontology` | 1 |
| `generated_benchmarks` | 69 |
| `queries` | 19 |
| `docs` | 12 |
| `archive` | 94 |
| `build` | 14 |
| `dist` | 1 |
| `[root]` | 5 |

The `archive/` folder contains historical inputs and generated datasets.
`build/` and `dist/` contain PyInstaller artifacts and should normally be
excluded from the Git repository or moved to GitHub Releases as appropriate.
The `.spec` file may be kept as a reproducible build recipe.

## SHA-256 fingerprints

Hashes below are **recomputed from the exact bytes** in this updated snapshot,
not copied from the older October 30 inventory. File sizes are uncompressed.

| File (relative to `benchmark/`) | SHA-256 | Bytes |
|---|---|---:|
| `generators/parametric_benchmark_generator_Final.py` | `e2bc2990759be094959716b74c28b81bf57022ae500b2d4669d6febd41d4f222` | 84,908 |
| `generators/taxonomy.py` | `b47cdaf021441154d9a32110a7461dd47032d0b5f70fa8ea02a5da1c476d7bdf` | 1,998 |
| `generators/filterIndividuals_mapped.py` | `a5619be10b8811806990df189a64abb1a4a64d154265cd32ae846e3390993089` | 7,730 |
| `generators/translateToOntologyComplete.py` | `bb923ba8700b4398935ab4b4f1f81a08c4a7eaab528533e541ed9bffe9cce0d1` | 15,806 |
| `ontology/animal_taxonomy_ontology_complete.owl` | `aded35af3c2180d96f71f431798db645df0a7de85780f9c4d6a49085ef86f9b9` | 5,348,672 |
| `data/processed/taxonomy_normalized.tsv` | `90034054d9472928ed5c03bfdb71183a91de7140ca33c42070292fc3d69e8e96` | 77,789 |
| `data/processed/animalIndividuals_filtered.tsv` | `8cd7cd6ec24960504d0acef62cc684ee1f0114ba5ea0139794e8d422d770e9b3` | 2,305,925 |
| `data/processed/animalsNew_filtered.tsv` | `4f6801c9ca2a39e79d4a1a4a7edb7cb552ea60488330d456c80772160ca41c71` | 416,753 |
| `data/src/AnimalHierarchy.tsv` | `41e0c3d40c62b23db62debb385ad1716cf54e2d337f14861d5c184dbe7a01b96` | 575,472 |
| `README.md` | `5dea87e4dd59e0ca7c7de0cb08b7c8c9cd86c1bc5428dac2d91c5ff77a4292eb` | 6,104 |
| `BenchmarkGenerator.spec` | `8c701889cc4c3662148ebe7ca6a1ee4cb4b5fb3bac36ce6288826f2e64348524` | 971 |
| `requirements.txt` | `ddeed8b937edab116f0dabf3a9995aaf88e390ae0aae665cdb67452cc0a7dbf4` | 353 |
| `LICENSE` | `f424c8bbeea703edf3c0659a64ead0bd280b706ffc74052c19e8e4ed7ea5518c` | 1,534 |

The previously documented hashes that changed in this ZIP were those of the
parametric generator, full ontology, and three processed TSV datasets. The
other four hashes from the original nine-file baseline remained unchanged.
The new README, requirements file, and license fingerprints reflect this
updated snapshot. This document deliberately does not include its own hash,
which would be self-referential.

## Verify fingerprints locally

Run these commands from the **`benchmark/` project root**.

PowerShell:

```powershell
Get-FileHash generators\parametric_benchmark_generator_Final.py -Algorithm SHA256
Get-FileHash ontology\animal_taxonomy_ontology_complete.owl -Algorithm SHA256
Get-FileHash requirements.txt -Algorithm SHA256
Get-FileHash LICENSE -Algorithm SHA256
```

Linux/macOS:

```bash
sha256sum generators/parametric_benchmark_generator_Final.py
sha256sum ontology/animal_taxonomy_ontology_complete.owl
sha256sum requirements.txt LICENSE
```

SHA-256 equality proves **byte-for-byte file identity**, not equivalence of
OWL semantics or correct query answers. RDF/XML serialization may produce
different bytes for graphs containing the same RDF triples.

## Runtime environment and release metadata

The `requirements.txt` pins the two third-party Python packages actually
imported by the generators: `pandas==2.2.3` and `rdflib==7.5.0`.
These versions were available in the validation environment running
**Python 3.13.5 (Linux)**. They are *tested versions for this snapshot*,
not a claim about the author's original Windows development environment.
The GUI also needs Tkinter, which is provided by the system Python/Tk package,
and PyInstaller is optional for packaging only.

Before publishing an official version, record the following alongside the
release and benchmark experiments:

```text
Project release/tag:      <assign at release>
Git commit:               <commit hash after publishing>
Release date:             2026-11-03 (snapshot date; update when released)
Python:                  <runtime version in experiments>
pandas / RDFLib:         <installed and verified versions>
PyInstaller:             <version if building Windows executable>
Dataset SHA-256:         <hash of the ontology actually used>
Datalog translator:      <repository/tag/commit, if applicable>
Reasoner/runtime:        <i-DLV / Souffle versions and execution options>
```

### Licensing scope

`LICENSE` uses the MIT License for the project's **original code and
documentation**, not for third-party or derived data files. Confirm and
document the distribution rights of files in `data/`, `ontology/`,
`generated_benchmarks/`, and `archive/` before releasing these datasets.
