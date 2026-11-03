from pathlib import Path
import re
import pandas as pd

# Percorsi assoluti ricavati dalla posizione dello script, non dalla cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "data" / "src"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
BENCHMARKS_DIR = PROJECT_ROOT / "generated_benchmarks"

# File di input
INDIVIDUALS_FILE = SOURCE_DIR / "animalIndividuals.tsv"
ANIMALS_NEW_FILE = SOURCE_DIR / "AnimalsNew.tsv"
TAXONOMY_FILE = PROCESSED_DIR / "taxonomy_normalized.tsv"

# File di output
INDIVIDUALS_OUTPUT_FILE = PROCESSED_DIR / "animalIndividuals_filtered.tsv"
ANIMALS_NEW_OUTPUT_FILE = PROCESSED_DIR / "animalsNew_filtered.tsv"

WIKIDATA_ITEM_RE = re.compile(r"^https?://www\.wikidata\.org/entity/Q\d+$")


def read_tsv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    """Legge un TSV e verifica che contenga le colonne richieste."""
    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {path}")

    dataframe = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    missing_columns = required_columns.difference(dataframe.columns)

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Nel file {path} mancano le colonne: {missing}")

    # Normalizza gli spazi nelle colonne testuali.
    for column in dataframe.columns:
        dataframe[column] = dataframe[column].str.strip()

    return dataframe


def non_empty_values(dataframe: pd.DataFrame, column: str) -> set[str]:
    """Restituisce i valori non vuoti di una colonna."""
    return {value for value in dataframe[column] if value}


def is_wikidata_item(value: str) -> bool:
    """True se value identifica un normale item Wikidata Q... ."""
    return bool(WIKIDATA_ITEM_RE.fullmatch(value))


def build_class_to_taxon_mapping(
    animals_new: pd.DataFrame,
    taxonomy_taxa: set[str],
) -> pd.DataFrame:
    """
    Costruisce la tabella class -> taxon usando AnimalsNew.tsv.

    Vengono mantenuti solo i taxon che appartengono effettivamente a
    taxonomy_normalized.tsv. Una class può corrispondere a più taxon:
    in quel caso il mapping conserva tutte le associazioni distinte.
    """
    mapping = animals_new[["class", "taxon"]].copy()
    mapping = mapping[
        (mapping["class"] != "")
        & (mapping["taxon"] != "")
        & (mapping["taxon"].isin(taxonomy_taxa))
    ]

    return mapping.drop_duplicates(subset=["class", "taxon"])


def process_individuals(
    individuals: pd.DataFrame,
    taxonomy_taxa: set[str],
    class_to_taxon: pd.DataFrame,
) -> pd.DataFrame:
    """
    Produce animalIndividuals_filtered.tsv con una semantica uniforme:

        x     = individuo
        class = taxon effettivo della tassonomia

    Caso 1: se la class originale è già un taxon della tassonomia, la riga
    viene mantenuta direttamente.

    Caso 2: se la class non è un taxon ma compare come class in AnimalsNew,
    viene sostituita con il/i taxon associati da AnimalsNew.tsv.
    """
    individuals = individuals[(individuals["x"] != "") & (individuals["class"] != "")].copy()

    # Individui già collegati direttamente a un taxon della tassonomia.
    direct = individuals[individuals["class"].isin(taxonomy_taxa)][["x", "class"]].copy()

    mapping_classes = set(class_to_taxon["class"])

    # Righe la cui classe Wikidata non è un taxon, ma è mappabile tramite
    # AnimalsNew.tsv.
    source_to_map = individuals[
        (~individuals["class"].isin(taxonomy_taxa))
        & (individuals["class"].isin(mapping_classes))
    ][["x", "class"]].copy()

    # Join class -> taxon. Se una class ha più taxon, vengono prodotte più
    # coppie individuo-taxon: non scegliamo arbitrariamente un solo taxon.
    mapped = source_to_map.merge(
        class_to_taxon,
        on="class",
        how="inner",
        validate="many_to_many",
    )
    mapped = mapped[["x", "taxon"]].rename(columns={"taxon": "class"})

    # Un'unica asserzione per ogni coppia individuo-taxon.
    result = pd.concat([direct, mapped], ignore_index=True)
    result = result.drop_duplicates(subset=["x", "class"])

    discarded = individuals[
        (~individuals["class"].isin(taxonomy_taxa))
        & (~individuals["class"].isin(mapping_classes))
    ]

    multi_mapping = (
        class_to_taxon.groupby("class")["taxon"]
        .nunique()
        .loc[lambda values: values > 1]
        .sort_values(ascending=False)
    )

    print("\n=== animalIndividuals.tsv ===")
    print(f"Righe originali: {len(individuals)}")
    print(f"Asserzioni già su taxon validi: {len(direct)}")
    print(f"Righe sorgente recuperate tramite mapping class -> taxon: {len(source_to_map)}")
    print(f"Asserzioni generate dal mapping: {len(mapped.drop_duplicates())}")
    print(f"Classi intermedie effettivamente recuperate: {source_to_map['class'].nunique()}")
    print(f"Righe scartate perché non mappabili: {len(discarded)}")
    print(f"Asserzioni finali individuo-taxon: {len(result)}")

    if not multi_mapping.empty:
        used_multi = multi_mapping[multi_mapping.index.isin(set(source_to_map["class"]))]
        if not used_multi.empty:
            print("\nClassi recuperate associate a più taxon:")
            for class_iri, count in used_multi.items():
                print(f"  {class_iri} -> {count} taxon")

    result.to_csv(INDIVIDUALS_OUTPUT_FILE, sep="\t", index=False)
    print(f"File creato: {INDIVIDUALS_OUTPUT_FILE}")

    return result


def process_animals_new(
    animals_new: pd.DataFrame,
    taxonomy_taxa: set[str],
) -> pd.DataFrame:
    """
    Filtra AnimalsNew.tsv mantenendo solo:
      - taxon presenti nella tassonomia normalizzata;
      - normali item Wikidata Q... come individui.

    La colonna class viene mantenuta nel TSV per documentare la provenienza,
    ma nella costruzione dell'OWL l'asserzione corretta è animal rdf:type taxon.
    """
    valid_taxon_mask = animals_new["taxon"].isin(taxonomy_taxa)
    valid_animal_mask = animals_new["animal"].map(is_wikidata_item)

    filtered = animals_new[valid_taxon_mask & valid_animal_mask].copy()
    filtered = filtered.drop_duplicates(subset=["class", "taxon", "animal"])

    lexical_or_non_item = animals_new[valid_taxon_mask & ~valid_animal_mask]

    print("\n=== AnimalsNew.tsv ===")
    print(f"Righe originali: {len(animals_new)}")
    print(f"Righe con taxon presente nella tassonomia: {int(valid_taxon_mask.sum())}")
    print(
        "Righe escluse perché animal non è un item Wikidata Q...: "
        f"{len(lexical_or_non_item)}"
    )
    print(f"Righe filtrate finali: {len(filtered)}")

    filtered.to_csv(ANIMALS_NEW_OUTPUT_FILE, sep="\t", index=False)
    print(f"File creato: {ANIMALS_NEW_OUTPUT_FILE}")

    return filtered


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    taxonomy = read_tsv(TAXONOMY_FILE, {"taxon"})
    individuals = read_tsv(INDIVIDUALS_FILE, {"x", "class"})
    animals_new = read_tsv(ANIMALS_NEW_FILE, {"class", "taxon", "animal"})

    taxonomy_taxa = non_empty_values(taxonomy, "taxon")
    class_to_taxon = build_class_to_taxon_mapping(animals_new, taxonomy_taxa)

    print("=== Mapping ===")
    print(f"Taxon nella tassonomia: {len(taxonomy_taxa)}")
    print(f"Classi Wikidata mappabili: {class_to_taxon['class'].nunique()}")
    print(f"Associazioni class -> taxon distinte: {len(class_to_taxon)}")

    process_individuals(
        individuals=individuals,
        taxonomy_taxa=taxonomy_taxa,
        class_to_taxon=class_to_taxon,
    )

    process_animals_new(
        animals_new=animals_new,
        taxonomy_taxa=taxonomy_taxa,
    )


if __name__ == "__main__":
    main()
