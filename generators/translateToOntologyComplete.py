from pathlib import Path

import pandas as pd
from rdflib import Graph, Literal, Namespace, URIRef, RDF, RDFS, OWL


# Percorsi assoluti ricavati dalla posizione dello script, non dalla cwd.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = PROJECT_ROOT / "data" / "src"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
BENCHMARKS_DIR = PROJECT_ROOT / "generated_benchmarks"


TAXONOMY_FILE = PROCESSED_DIR / "taxonomy_normalized.tsv"
INDIVIDUALS_FILE = PROCESSED_DIR / "animalIndividuals_filtered.tsv"
ANIMALS_NEW_FILE = PROCESSED_DIR / "animalsNew_filtered.tsv"
PREDATOR_RELATIONS_FILE = SOURCE_DIR / "predator_relations.tsv"
COEXISTS_RELATIONS_FILE = SOURCE_DIR / "coexists_relations.tsv"
DISJOINT_CLASSES_FILE = SOURCE_DIR / "disjoint_classes.tsv"
OUTPUT_FILE = ONTOLOGY_DIR / "animal_taxonomy_ontology_complete.owl"

EX = Namespace("http://example.org/taxonomy/")
WD = Namespace("http://www.wikidata.org/entity/")

g = Graph()

g.bind("ex", EX)
g.bind("wd", WD)
g.bind("owl", OWL)
g.bind("rdf", RDF)
g.bind("rdfs", RDFS)

Taxon = EX.Taxon
TaxonomicRank = EX.TaxonomicRank
#hasRank = EX.hasRank

hasDirectParentTaxon = EX.hasDirectParentTaxon
hasDirectChildTaxon = EX.hasDirectChildTaxon

# Object property relative alla predazione
predatorOf = EX.predatorOf
landPredatorOf = EX.landPredatorOf
aerialPredatorOf = EX.aerialPredatorOf
aquaticPredatorOf = EX.aquaticPredatorOf

# Proprietà inverse
preyOf = EX.preyOf
landPreyOf = EX.landPreyOf
aerialPreyOf = EX.aerialPreyOf
aquaticPreyOf = EX.aquaticPreyOf

coexistsWith = EX.coexistsWith

g.add((Taxon, RDF.type, OWL.Class))
g.add((TaxonomicRank, RDF.type, OWL.Class))
#g.add((hasRank, RDF.type, OWL.ObjectProperty))

# Dichiarazione delle proprietà di predazione
for property_iri in (
    predatorOf,
    landPredatorOf,
    aerialPredatorOf,
    aquaticPredatorOf,
):
    g.add((property_iri, RDF.type, OWL.ObjectProperty))
    g.add((property_iri, RDFS.domain, Taxon))
    g.add((property_iri, RDFS.range, Taxon))


# Gerarchia delle proprietà
g.add((landPredatorOf, RDFS.subPropertyOf, predatorOf))
g.add((aerialPredatorOf, RDFS.subPropertyOf, predatorOf))
g.add((aquaticPredatorOf, RDFS.subPropertyOf, predatorOf))

# Etichette leggibili
g.add((predatorOf, RDFS.label, Literal("predator of", lang="en")))
g.add((landPredatorOf, RDFS.label, Literal("land predator of", lang="en")))
g.add((aerialPredatorOf, RDFS.label, Literal("aerial predator of", lang="en")))
g.add((aquaticPredatorOf, RDFS.label, Literal("aquatic predator of", lang="en")))

# Dichiarazione delle proprietà inverse.
# Domain e range non vengono aggiunti esplicitamente:
# vogliamo sfruttare l'assioma inverseOf durante il reasoning.
for property_iri in (
    preyOf,
    landPreyOf,
    aerialPreyOf,
    aquaticPreyOf,
):
    g.add((property_iri, RDF.type, OWL.ObjectProperty))

# Relazioni inverse
g.add((predatorOf, OWL.inverseOf, preyOf))
g.add((landPredatorOf, OWL.inverseOf, landPreyOf))
g.add((aerialPredatorOf, OWL.inverseOf, aerialPreyOf))
g.add((aquaticPredatorOf, OWL.inverseOf, aquaticPreyOf))

g.add((preyOf, RDFS.label, Literal("prey of", lang="en")))
g.add((landPreyOf, RDFS.label, Literal("land prey of", lang="en")))
g.add((aerialPreyOf, RDFS.label, Literal("aerial prey of", lang="en")))
g.add((aquaticPreyOf, RDFS.label, Literal("aquatic prey of", lang="en")))

# Relazioni di parentela tassonomica diretta
g.add((hasDirectParentTaxon, RDF.type, OWL.ObjectProperty))
g.add((hasDirectParentTaxon, RDF.type, OWL.IrreflexiveProperty))
g.add((hasDirectParentTaxon, OWL.propertyDisjointWith, hasDirectChildTaxon))

g.add((hasDirectParentTaxon, RDFS.domain, Taxon))
g.add((hasDirectParentTaxon, RDFS.range, Taxon))

g.add((
    hasDirectParentTaxon,
    RDFS.label,
    Literal("has direct parent taxon", lang="en")
))

# La relazione inversa viene dichiarata ma non materializzata nell'ABox:
# hasDirectChildTaxon deve essere ricavata dal reasoning a partire da
# hasDirectParentTaxon.
g.add((hasDirectChildTaxon, RDF.type, OWL.ObjectProperty))
g.add((hasDirectParentTaxon, OWL.inverseOf, hasDirectChildTaxon))

g.add((
    hasDirectChildTaxon,
    RDFS.label,
    Literal("has direct child taxon", lang="en")
))


# -------------------------
# Proprietà di coesistenza
# -------------------------

g.add((coexistsWith, RDF.type, OWL.ObjectProperty))
g.add((coexistsWith, RDF.type, OWL.ReflexiveProperty))

g.add((
    coexistsWith,   
    RDFS.label,
    Literal("coexists with", lang="en")
))


def iri(value: str) -> URIRef:
    value = value.strip()

    if value.startswith("http://") or value.startswith("https://"):
        return URIRef(value)

    if value.startswith("wd:"):
        return WD[value.removeprefix("wd:")]

    return EX[value.replace(" ", "_").replace("/", "_")]


# -------------------------
# 1. TBox + metamodeling
# -------------------------

taxonomy = pd.read_csv(
    TAXONOMY_FILE,
    sep="\t",
    dtype=str,
).fillna("")

required_taxonomy_columns = {"taxon", "parent", "rank", "name"}
missing_taxonomy_columns = required_taxonomy_columns - set(taxonomy.columns)

if missing_taxonomy_columns:
    raise ValueError(
        "Il file della tassonomia non contiene le colonne richieste: "
        f"{sorted(missing_taxonomy_columns)}"
    )

for _, row in taxonomy.iterrows():
    taxon = row["taxon"].strip()
    parent = row["parent"].strip()
    rank = row["rank"].strip()
    name = row["name"].strip()

    if not taxon:
        continue

    taxon_iri = iri(taxon)

    # Taxon come classe OWL
    g.add((taxon_iri, RDF.type, OWL.Class))

    # Taxon anche come istanza della metaclasse ex:Taxon
    g.add((taxon_iri, RDF.type, Taxon))

    # Nome scientifico del taxon
    if name:
        g.add((taxon_iri, RDFS.label, Literal(name)))

    # Rank tassonomico + metamodeling sui ranghi
    if rank:
        rank_iri = iri(rank)

        # Il rank è una classe OWL: Species, Genus, Family, Order, ...
        # diventano quindi vere metaclassi.
        g.add((rank_iri, RDF.type, OWL.Class))

        # Il rank è anche un'istanza della metaclasse generale TaxonomicRank.
        # Esempio: Species rdf:type TaxonomicRank.
        g.add((rank_iri, RDF.type, TaxonomicRank))

        # Ogni rank tassonomico è una specializzazione di Taxon.
        # Esempio: Species rdfs:subClassOf Taxon.
        g.add((rank_iri, RDFS.subClassOf, Taxon))

        # Mantiene l'informazione originale sul rango.
        # g.add((taxon_iri, hasRank, rank_iri))

        # Metamodeling:
        # il taxon, che è già una classe OWL, diventa anche istanza
        # della metaclasse corrispondente al proprio rango.
        # Esempio:
        #   Panthera_leo rdf:type owl:Class
        #   Panthera_leo rdf:type Species
        g.add((taxon_iri, RDF.type, rank_iri))

    # Il parent tassonomico viene rappresentato come superclasse
    if parent:
        parent_iri = iri(parent)

        g.add((parent_iri, RDF.type, OWL.Class))
        g.add((parent_iri, RDF.type, Taxon))
        g.add((taxon_iri, RDFS.subClassOf, parent_iri))
        g.add((taxon_iri, hasDirectParentTaxon, parent_iri))


# -------------------------
# 3. ABox: individui animali
# -------------------------

def read_tsv(path: Path, required_columns: set[str]) -> pd.DataFrame:
    """Legge un TSV e controlla che contenga le colonne richieste."""
    if not path.exists():
        raise FileNotFoundError(f"File non trovato: {path}")

    dataframe = pd.read_csv(path, sep="\t", dtype=str).fillna("")
    missing_columns = required_columns - set(dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Il file {path} non contiene le colonne richieste: "
            f"{sorted(missing_columns)}"
        )

    return dataframe


# -------------------------
# 2. TBox: disjointness tra classi
# -------------------------

disjoint_classes = read_tsv(
    DISJOINT_CLASSES_FILE,
    {"class1", "class2"},
)

disjoint_assertions = 0
seen_disjoint_pairs = set()

for _, row in disjoint_classes.iterrows():
    class1 = row["class1"].strip()
    class2 = row["class2"].strip()

    if not class1 or not class2:
        continue

    class1_iri = iri(class1)
    class2_iri = iri(class2)

    if class1_iri == class2_iri:
        raise ValueError(
            f"Disjointness non valida: una classe non può essere disjoint da se stessa: {class1}"
        )

    # Le coppie del TSV devono riferirsi a classi già appartenenti alla
    # tassonomia caricata, senza introdurre nuove classi accidentalmente.
    if (class1_iri, RDF.type, OWL.Class) not in g:
        raise ValueError(f"Classe disjoint non presente nella tassonomia: {class1}")
    if (class2_iri, RDF.type, OWL.Class) not in g:
        raise ValueError(f"Classe disjoint non presente nella tassonomia: {class2}")

    # owl:disjointWith è simmetrico: evita di aggiungere due volte la
    # stessa coppia se il TSV contenesse accidentalmente entrambe le direzioni.
    pair_key = frozenset((str(class1_iri), str(class2_iri)))
    if pair_key in seen_disjoint_pairs:
        continue

    seen_disjoint_pairs.add(pair_key)
    g.add((class1_iri, OWL.disjointWith, class2_iri))
    disjoint_assertions += 1

print(f"Assiomi owl:disjointWith aggiunti: {disjoint_assertions}")


def is_wikidata_item(value: str) -> bool:
    """
    Restituisce True per gli item Wikidata Q... .

    animalsNew_filtered.tsv contiene anche alcuni URI L...-S... che
    identificano sensi lessicali Wikidata e non individui animali.
    """
    prefix = "http://www.wikidata.org/entity/"
    if not value.startswith(prefix):
        return True

    identifier = value.removeprefix(prefix)
    return identifier.startswith("Q") and identifier[1:].isdigit()


# File storico: x = individuo, class = taxon.
individuals = read_tsv(INDIVIDUALS_FILE, {"x", "class"})
individuals_normalized = individuals[["x", "class"]].rename(
    columns={"x": "individual", "class": "taxon"}
)
individuals_normalized["source"] = INDIVIDUALS_FILE.name

# Nuovo file: animal = individuo, taxon = classe tassonomica.
# La colonna "class" è la classe Wikidata intermedia usata nella query
# P31 -> P13176 e non va usata come classe OWL dell'animale.
animals_new = read_tsv(ANIMALS_NEW_FILE, {"class", "taxon", "animal"})
animals_new_normalized = animals_new[["animal", "taxon"]].rename(
    columns={"animal": "individual"}
)
animals_new_normalized["source"] = ANIMALS_NEW_FILE.name

# Normalizza gli spazi prima di unire i due insiemi di asserzioni.
for dataframe in (individuals_normalized, animals_new_normalized):
    dataframe["individual"] = dataframe["individual"].str.strip()
    dataframe["taxon"] = dataframe["taxon"].str.strip()

# Elimina righe incomplete.
individuals_normalized = individuals_normalized[
    (individuals_normalized["individual"] != "")
    & (individuals_normalized["taxon"] != "")
]
animals_new_normalized = animals_new_normalized[
    (animals_new_normalized["individual"] != "")
    & (animals_new_normalized["taxon"] != "")
]

# Esclude da animalsNew i sensi lessicali Wikidata L...-S..., che non
# rappresentano normali item/individui animali.
valid_new_mask = animals_new_normalized["individual"].map(is_wikidata_item)
discarded_new = animals_new_normalized[~valid_new_mask]
animals_new_normalized = animals_new_normalized[valid_new_mask]

if not discarded_new.empty:
    print(
        f"Escluse {len(discarded_new)} righe da {ANIMALS_NEW_FILE.name} "
        "perché l'individuo non è un item Wikidata Q..."
    )

# Unisce i due file. source serve solo per le statistiche e non entra nell'OWL.
all_individuals = pd.concat(
    [individuals_normalized, animals_new_normalized],
    ignore_index=True,
)

raw_assertions = len(all_individuals)

# La stessa coppia individuo-taxon deve produrre una sola asserzione rdf:type.
all_individuals = all_individuals.drop_duplicates(
    subset=["individual", "taxon"]
)

for _, row in all_individuals.iterrows():
    individual_iri = iri(row["individual"])
    class_iri = iri(row["taxon"])

    # Dichiara la classe tassonomica.
    g.add((class_iri, RDF.type, OWL.Class))

    # ABox: individuo appartenente al taxon.
    g.add((individual_iri, RDF.type, class_iri))

print(
    "ABox individui: "
    f"{len(individuals_normalized)} asserzioni da {INDIVIDUALS_FILE.name}, "
    f"{len(animals_new_normalized)} da {ANIMALS_NEW_FILE.name}; "
    f"{len(all_individuals)} coppie individuo-taxon uniche "
    f"({raw_assertions - len(all_individuals)} duplicati eliminati)."
)
print(
    f"Individui animali distinti nell'ABox: "
    f"{all_individuals['individual'].nunique()}"
)


# -------------------------
# 4. ABox: relazioni di predazione
# -------------------------

predator_relations = pd.read_csv(
    PREDATOR_RELATIONS_FILE,
    sep="\t",
    dtype=str,
).fillna("")

# Normalizza eventuali spazi nei nomi delle colonne
predator_relations.columns = [
    column.strip() for column in predator_relations.columns
]

required_predator_columns = {"predator", "prey", "role"}
missing_predator_columns = (
    required_predator_columns - set(predator_relations.columns)
)

if missing_predator_columns:
    raise ValueError(
        "Il file delle relazioni predatorie non contiene le colonne richieste: "
        f"{sorted(missing_predator_columns)}"
    )

role_to_property = {
    "predator": predatorOf,
    "predatorOf": predatorOf,
    "landPredatorOf": landPredatorOf,
    "aerialPredatorOf": aerialPredatorOf,
    "aquaticPredatorOf": aquaticPredatorOf,
    # Alias tollerato nel caso sia rimasto il nome usato inizialmente
    "aquaticaPredatorOf": aquaticPredatorOf,
}

unknown_roles = set()

for _, row in predator_relations.iterrows():
    predator = row["predator"].strip()
    prey = row["prey"].strip()
    role = row["role"].strip()

    if not predator or not prey or not role:
        continue

    property_iri = role_to_property.get(role)

    if property_iri is None:
        unknown_roles.add(role)
        continue

    predator_iri = iri(predator)
    prey_iri = iri(prey)

    # Predator e preda sono taxa usati anche come individui OWL
    # della metaclasse ex:Taxon.
    g.add((predator_iri, RDF.type, OWL.Class))
    g.add((predator_iri, RDF.type, Taxon))
    g.add((prey_iri, RDF.type, OWL.Class))
    g.add((prey_iri, RDF.type, Taxon))

    # Tripla: predator property prey
    g.add((predator_iri, property_iri, prey_iri))

if unknown_roles:
    raise ValueError(
        "Nel file delle relazioni predatorie sono presenti ruoli sconosciuti: "
        f"{sorted(unknown_roles)}"
    )


# -------------------------
# 5. ABox: relazioni di coesistenza
# -------------------------

coexists_relations = read_tsv(
    COEXISTS_RELATIONS_FILE,
    {"taxon1", "taxon2"},
)

coexists_assertions = 0

for _, row in coexists_relations.iterrows():
    taxon1 = row["taxon1"].strip()
    taxon2 = row["taxon2"].strip()

    if not taxon1 or not taxon2:
        continue

    taxon1_iri = iri(taxon1)
    taxon2_iri = iri(taxon2)

    # I taxa sono utilizzati sia come classi OWL sia come individui
    # della metaclasse Taxon.
    g.add((taxon1_iri, RDF.type, OWL.Class))
    g.add((taxon1_iri, RDF.type, Taxon))

    g.add((taxon2_iri, RDF.type, OWL.Class))
    g.add((taxon2_iri, RDF.type, Taxon))

    # ABox:
    # taxon1 coexistsWith taxon2
    #
    # Non viene aggiunta automaticamente la relazione inversa
    # taxon2 coexistsWith taxon1.
    g.add((taxon1_iri, coexistsWith, taxon2_iri))

    coexists_assertions += 1

print(
    f"Relazioni coexistsWith aggiunte: "
    f"{coexists_assertions}"
)


# Salva in RDF/XML con estensione .owl
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
g.serialize(
    destination=str(OUTPUT_FILE),
    format="xml",
)

print(f"Creato file OWL: {OUTPUT_FILE}")
print(f"Numero triple RDF: {len(g)}")