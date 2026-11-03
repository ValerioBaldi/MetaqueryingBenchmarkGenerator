# 01 — Installation, execution, and your first benchmark

[Back to README](../README.md)

## Requirements

- Windows with **Python 3.10+ recommended** (the code uses `str.removeprefix`, type annotations, and modern Python syntax), or Linux with Tkinter available.
- Python dependencies: `pandas`, `rdflib`. `tkinter` is bundled with many desktop Python installations, but not all.
- Sufficient disk space for RDF/XML files and benchmark outputs; RAM usage depends on the size of the RDFLib graph.
- **Java, i-DLV, and Soufflé are not required** for dataset generation alone. They are external to the documented folder.

Windows PowerShell:

```powershell
cd C:\path\to\project\benchmark
py --version
py -m pip install pandas rdflib
py -c "import pandas, rdflib, tkinter; print('Dependencies OK')"
```

Linux/WSL, with graphical desktop support:

```bash
cd /path/to/project/benchmark
python3 -m pip install pandas rdflib
python3 -c 'import pandas, rdflib, tkinter; print("Dependencies OK")'
```

On Ubuntu, install `python3-tk` with `apt` if Tkinter is missing. WSL needs a working graphical display to show the GUI; otherwise, use the Windows version.

## Launch the existing generator

```powershell
py generators\parametric_benchmark_generator_Final.py
```

The default paths are derived from the script's location, whether you start it from the project root or another working directory. On startup, the GUI attempts to analyze the default OWL file if it exists. Use **Analyze dataset** to repeat the analysis after choosing a different ontology.

### Recommended first experiment

1. Check the **FULL ontology** input and the **Source ontology statistics** panel.
2. Click **A1 · 10%**. This selects all classes, stratified 10% sampling, seed 42, and all semantic features.
3. Select an empty output directory, for example `generated_benchmarks/quick_test/`.
4. Click **Generate benchmark**.
5. Check the log and phase completion; confirm that `A1_abox.owl` and the four related files (`_config.json`, `_stats.tsv`, `_semantic_report.txt`, `_semantic_report.json`) were created.
6. Read the text report and compare the resulting counts with the input ontology preview.

**File naming:** the A1 preset sets `name = A1_abox`, so new outputs are named `A1_abox.*`. The historical `generated_benchmarks/ABox/` directory also contains `A1.owl`. Historical names and metadata have not been retroactively normalized.

## Rebuild the dataset from scratch

```powershell
py generators\taxonomy.py
py generators\filterIndividuals_mapped.py
py generators\translateToOntologyComplete.py
```

Follow this order:

1. `taxonomy.py` reads `data/src/taxonomiesNew/*.tsv` and produces `data/processed/taxonomy_normalized.tsv`.
2. `filterIndividuals_mapped.py` uses the individual data sources and normalized taxonomy to produce two filtered TSV files.
3. `translateToOntologyComplete.py` combines processed TSVs and relationship tables into `ontology/animal_taxonomy_ontology_complete.owl`.
4. The parametric generator can then read the completed OWL file.

**Rebuilding overwrites destination files.** Back up source data and any ontology already used in published or archived experiments.

## Protecting output files

**Overwrite files with the same name** is disabled by default. On a naming collision, generation stops without overwriting the five destination files. If you enable overwriting, newly generated data replace the corresponding files. Prefer separate directories for different runs or experimental campaigns, and retain their reports and versions.

The generator **does not have a documented batch CLI** for generating all presets at once: its GUI produces one benchmark per operation. PyInstaller's `--onefile` flag applies to Windows packaging only and is not a generator command.

## Quick OWL reading check

```powershell
py -c "from rdflib import Graph; g=Graph();g.parse('ontology/animal_taxonomy_ontology_complete.owl');print('RDF triples:',len(g))"
```

The expected result for this version is `RDF triples: 36002`. This verifies that RDFLib can read the file and reports its triple count; it is **not** a formal OWL 2 QL compliance test or a query-answering correctness test.
