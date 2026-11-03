# 03 — Ontology construction and semantic model

[Back to README](../README.md)

## Objective

`generators/translateToOntologyComplete.py` translates TSV data into an **RDF graph**, then serializes it as OWL in RDF/XML format. Its output is `ontology/animal_taxonomy_ontology_complete.owl`.

The pipeline **does not perform OWL inference**. It creates explicit triples that may subsequently be translated and evaluated using external tools.

## Entities and namespaces

- `ex:` → `http://example.org/taxonomy/`
- `wd:` → `http://www.wikidata.org/entity/`
- `ex:Taxon` and `ex:TaxonomicRank` are declared as `owl:Class`.
- A taxon may be declared both an `owl:Class` and an instance of `ex:Taxon`, as well as an instance of a taxonomic-rank class.

Illustrative pattern (example names only):

```turtle
ex:Taxon rdf:type owl:Class .
ex:Species rdf:type owl:Class .
ex:Species rdfs:subClassOf ex:Taxon .
wd:Q140 rdf:type owl:Class .
wd:Q140 rdf:type ex:Taxon .
wd:Q140 rdf:type ex:Species .
```

The same taxon identifier appears as both a class and an individual of a metaclass. The thesis's treatment of metamodeling depends on the downstream entailment regime; **the RDF file alone does not establish MSER semantics**.

## Processing stages

1. Declare special classes and the 11 object properties.
2. Add property hierarchies/axioms (inclusions, inverses, domain/range, role disjointness, reflexivity/irreflexivity).
3. Read the normalized taxonomy and emit class declarations, taxonomic-rank metaclasses, `rdfs:subClassOf`, and `hasDirectParentTaxon` triples.
4. Read `disjoint_classes.tsv` and validate eligible pairs.
5. Merge individuals from both filtered TSVs, removing duplicate pairs.
6. Read predation and coexistence tables, attaching relevant roles to taxa.
7. Serialize the graph in RDF/XML.

`animalsNew_filtered.tsv` retains the original `class` field for provenance, but the final assertion uses `animal rdf:type taxon`.

## Existing object properties

| Category | Properties | Notes |
|---|---|---|
| Predation | `predatorOf`, `landPredatorOf`, `aerialPredatorOf`, `aquaticPredatorOf` | Three specialized roles are subproperties of `predatorOf` |
| Inverse predation | `preyOf`, `landPreyOf`, `aerialPreyOf`, `aquaticPreyOf` | Inverses are declared but not materialized in the source ABox |
| Taxonomy | `hasDirectParentTaxon`, `hasDirectChildTaxon` | Child role is the inverse of parent role; parent role is declared irreflexive |
| Coexistence | `coexistsWith` | Declared reflexive; the generator adds only directions found in the TSV |

**Explicit** role assertions in the complete source graph:

| Property with explicit assertions | Triples |
|---|---:|
| `hasDirectParentTaxon` | 600 |
| `coexistsWith` | 50 |
| `predatorOf` | 24 |
| `landPredatorOf` | 31 |
| `aquaticPredatorOf` | 9 |
| `aerialPredatorOf` | 8 |
| **Total** | **722** |

The other five properties are declared but do not have explicit role assertions in the source graph. They may nevertheless contribute to inferred facts during downstream reasoning.

## Main axioms in the current version

| Axiom/triple type | Explicit count |
|---|---:|
| `rdfs:subClassOf` | 646 |
| `rdfs:subPropertyOf` | 3 |
| `owl:inverseOf` | 5 |
| `owl:disjointWith` | 50 |
| `owl:propertyDisjointWith` | 1 |
| `rdfs:domain` | 5 |
| `rdfs:range` | 5 |
| `owl:ReflexiveProperty` declarations | 1 |
| `owl:IrreflexiveProperty` declarations | 1 |

## TBox, ABox, and metamodeling

The ontology mixes schema axioms (such as class inclusions), assertions about ordinary individuals, and assertions that use a **class IRI as an individual** (`Taxon(Lion)` is the thesis's conceptual example). *Metamodeling* here means **using classes as individuals**, not merely maintaining a taxonomic hierarchy.

Role assertions also connect taxa, i.e. resources declared as classes in this dataset. This is useful for metaqueries and joins across semantic levels.

## OWL 2 QL compatibility: methodological warning

The dataset uses constructs such as `owl:ReflexiveProperty` and `owl:IrreflexiveProperty`, which **must not be assumed to be supported by the standard OWL 2 QL profile**. A generator name is not a formal OWL 2 QL conformance check. If an experiment requires strict compliance, separately filter or validate these constructs and record which axioms the Datalog translator accepts.

Likewise, **`rdf:type` statements between classes do not by themselves amount to standard Direct Semantics metamodeling**. Any MSER-specific interpretation belongs to the downstream translation/query layer.

## What the script does not do

- It does not access Wikidata online at runtime; it reads local TSVs.
- It does not compute transitive hierarchy closure or materialize inverse roles.
- It does not formally validate all OWL 2 QL restrictions.
- It does not answer queries or produce Datalog files.
- It does not currently incorporate `AnimalHierarchy.tsv`.
- It does not yet model properties as individuals or add metaproperties: `properties_used_as_individuals` is **0** in the current full ontology.
