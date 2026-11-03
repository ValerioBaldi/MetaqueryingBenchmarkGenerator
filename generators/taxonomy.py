from pathlib import Path
import pandas as pd

# Percorsi assoluti ricavati dalla posizione dello script, non dalla cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "data" / "src"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
BENCHMARKS_DIR = PROJECT_ROOT / "generated_benchmarks"

INPUT_DIR = SOURCE_DIR / "taxonomiesNew"
OUTPUT_FILE = PROCESSED_DIR / "taxonomy_normalized.tsv"

rows_out = []

for file_path in sorted(INPUT_DIR.glob("*.tsv")):
    df = pd.read_csv(
        file_path,
        sep="\t",
        dtype=str
    ).fillna("")

    # Normalizza i nomi delle colonne rimuovendo eventuali spazi
    df.columns = [column.strip() for column in df.columns]

    required_columns = {"taxon", "parent", "rank", "name"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"{file_path} non contiene le colonne richieste: "
            f"{sorted(missing_columns)}"
        )

    for _, row in df.iterrows():
        taxon = row["taxon"].strip()
        parent = row["parent"].strip()
        rank = row["rank"].strip()
        name = row["name"].strip()

        # Ignora eventuali righe senza taxon
        if not taxon:
            continue

        rows_out.append(
            {
                "taxon": taxon,
                "parent": parent,
                "rank": rank,
                "name": name,
            }
        )

out_df = pd.DataFrame(
    rows_out,
    columns=["taxon", "parent", "rank", "name"]
)

# Elimina righe completamente duplicate
out_df = out_df.drop_duplicates()

# Ordina il risultato per taxon, parent, rank e nome
out_df = out_df.sort_values(
    by=["taxon", "parent", "rank", "name"],
    ignore_index=True
)

OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

out_df.to_csv(
    OUTPUT_FILE,
    sep="\t",
    index=False
)

print(f"Creato file: {OUTPUT_FILE}")
print(f"Numero righe: {len(out_df)}")