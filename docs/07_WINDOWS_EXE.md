# 07 — Build and distribute the Windows `.exe`

[Back to README](../README.md)

## What is packaged?

`generators/parametric_benchmark_generator_Final.py` is the **graphical generator**. PyInstaller packages the Python interpreter and modules required to run that GUI as a Windows application. It does **not** automatically integrate the three preprocessing scripts (`taxonomy.py`, `filterIndividuals_mapped.py`, `translateToOntologyComplete.py`) into the GUI.

In the recommended packaging configuration, the **ontology remains an external file**, rather than being embedded in the executable. Users can select it through the interface.

## Build on Windows

Open PowerShell in the `benchmark/` directory and run:

```powershell
py --version
py -m pip install pandas rdflib pyinstaller
py -m PyInstaller --onefile --windowed --clean --noconfirm --name BenchmarkGenerator --collect-submodules rdflib.plugins.parsers --collect-submodules rdflib.plugins.serializers generators\parametric_benchmark_generator_Final.py
```

The expected output is `dist\BenchmarkGenerator.exe`. **Build on Windows to obtain a native Windows executable**; running PyInstaller on Linux/WSL does not automatically cross-compile a Windows `.exe`.

`--onefile` is suitable for this release. `--windowed` hides the terminal window. If startup errors are not visible, temporarily rebuild without `--windowed` to inspect exceptions.

## Portable paths for source and executable

The program does **not** contain hard-coded PC paths. All project-internal paths
are resolved relative to the project root, **not** the current working directory.

- Python source: `benchmark/generators/parametric_benchmark_generator_Final.py`
  automatically finds its parent project `benchmark/`.
- EXE in `benchmark/dist/BenchmarkGenerator.exe`: automatically finds its
  parent project `benchmark/`. **Do not move the executable** for this layout.
- EXE in `benchmark/BenchmarkGenerator.exe`: also supported when the `ontology/`
  directory is next to the executable.

The GUI's default fields use portable relative values:

```text
ontology/animal_taxonomy_ontology_complete.owl
generated_benchmarks/
```

Any relative path typed into the GUI is resolved from `benchmark/` regardless
of the folder from which the application was launched. **Browse** accepts
external absolute paths too. The generated `_config.json` stores relative
paths for project-internal files; for an external input/output it records only
the filename, marked by `input_owl_external`/`output_owl_external`. External
locations must be re-selected on another machine.

To compile using the included spec, open PowerShell in the project directory:

```powershell
py -m PyInstaller --clean --noconfirm BenchmarkGenerator.spec
```

For a **standalone deployment**, place the EXE alongside `ontology/` and
`generated_benchmarks/`, for example:

```text
BenchmarkApp/
├── BenchmarkGenerator.exe
├── ontology/
│   └── animal_taxonomy_ontology_complete.owl
└── generated_benchmarks/
```

The three preprocessing scripts are *not* packaged by this EXE. Existing
`dist/BenchmarkGenerator.exe` and `build/` artifacts in the archive were
compiled before these source changes and **must be rebuilt** to acquire them.
Do not distribute the stale `build/` folder; it may include local machine
paths from the original build.

## Windows acceptance checklist

1. Put the executable in the intended directory and launch it by double-clicking.
2. Select **Analyze dataset** and confirm that the ontology can be loaded.
3. Generate a fresh A1 configuration in a separate test folder.
4. Check successful completion in the log and the three output files (`.owl`, `_config.json`, `_stats.tsv`) produced by the generator supplied in this archive.
5. Inspect the JSON configuration and output paths.
6. Close and reopen the application; use Browse to select a second OWL file, analyze it, and create a second benchmark.
7. Before public distribution, repeat on another Windows machine **without a Python installation**.

**Validation status:** the Python scripts were checked; the supplied archive does **not** include a compiled `.exe` already tested on a destination Windows machine.

## Distribution limitations

PyInstaller executables are tied to the target operating system and architecture; they do not make the generator a web service. A new unsigned executable can trigger security warnings, which should be assessed rather than bypassed by disabling protections. For public distribution, consider code signing, a release version, licensing, and dependency reviews.
