# 10 — Glossary and conventions

[Back to README](../README.md)

- **OWL / RDF/XML:** the ontology language and serialization format used by generated `.owl` files.
- **RDF graph:** a set of `(subject, predicate, object)` triples managed by RDFLib.
- **TBox:** terminological/schema knowledge such as class/property inclusions. The project's TBox suites may retain some ABox data, so directory names alone do not specify exact content.
- **ABox:** assertions about individuals and relationships. In this benchmark, taxa used as individuals can also participate in role assertions.
- **OWL class:** an entity explicitly declared using `rdf:type owl:Class`.
- **Ordinary individual:** a subject typed with an OWL class that is not itself an OWL class, according to the current implementation. This does not include every RDF resource.
- **Metaclass:** a class classifying entities that are themselves used as classes, such as `ex:Taxon`.
- **Metamodeling:** use of one entity at multiple ontological levels; here chiefly classes as instances of metaclasses.
- **Metaproperty:** in a future extension, a property applied to entities representing other properties. This functionality is not yet present in the current dataset.
- **OWL 2 QL:** an OWL profile designed for efficient query answering; the generator does not automatically verify strict profile conformance.
- **MSER:** Metamodeling Semantics Entailment Regime, the semantic regime investigated in the downstream research work; not directly implemented by the generation GUI.
- **Explicit assertion:** a triple actually serialized into the source/output OWL file.
- **Inferred/materialized fact:** a consequence produced by a reasoner; not part of the generator's RDF statistics.
- **Primary stratum:** group assigned to an individual by taking its rarest eligible directly asserted class.
- **Seed:** value used with SHA-256 to produce deterministic pseudorandom sampling order.
- **Nested sampling:** the property that members selected at lower percentages are retained at larger percentages when all other parameters remain fixed.
- **Preset:** a predefined GUI control configuration, not an already generated dataset file.
- **Semantic report:** TXT/JSON description of enabled options and actual explicit RDF statistics.
