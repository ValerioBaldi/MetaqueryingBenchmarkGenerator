from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import queue
import sys
import shutil
import threading
import traceback
from collections import Counter, defaultdict
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef


# Project-relative paths; independent of the process working directory.
# The compiled EXE can remain in benchmark/dist/ or be placed in benchmark/.
def _get_project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        if exe_dir.name.lower() == "dist" and (exe_dir.parent / "ontology").is_dir():
            return exe_dir.parent
        return exe_dir
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _get_project_root()
SOURCE_DIR = PROJECT_ROOT / "data" / "src"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
ONTOLOGY_DIR = PROJECT_ROOT / "ontology"
BENCHMARKS_DIR = PROJECT_ROOT / "generated_benchmarks"


def resolve_user_path(raw: str) -> Path:
    """Resolve GUI paths relative to the project root, never the shell CWD."""
    value = raw.strip()
    if not value:
        raise ValueError("A file or directory path is required.")
    path = Path(value).expanduser()
    # abspath normalizes .. and . but preserves symlinks located in the project.
    return Path(os.path.abspath(path if path.is_absolute() else PROJECT_ROOT / path))


def portable_config_path(path: Path) -> str:
    """Do not store local absolute paths in portable configuration files."""
    resolved = Path(os.path.abspath(path))
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        # External files are selectable through Browse, but must be re-selected
        # on another computer. Store a filename instead of private local paths.
        return resolved.name


def is_external_path(path: Path) -> bool:
    try:
        Path(os.path.abspath(path)).relative_to(PROJECT_ROOT.resolve())
        return False
    except ValueError:
        return True


APP_TITLE = "Parametric OWL Benchmark Generator"

# Presets matching the benchmark sizes defined previously.
# A5 and T4 use the actual FULL size of the selected ontology.
ABOX_PRESETS = {
    "A1": 10,
    "A2": 25,
    "A3": 50,
    "A4": 75,
    "A5": 100,
}

TBOX_PRESETS = {
    "T1": 150,
    "T2": 300,
    "T3": 450,
    "T4": None,
}

DEFAULT_TBOX_INDIVIDUAL_PERCENTAGE = 25

EX = Namespace("http://example.org/taxonomy/")


# ============================================================
# Helper deterministici
# ============================================================

def stable_hash(value: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}|{value}".encode("utf-8")).hexdigest()


def deterministic_uniform(value: str, seed: int) -> float:
    digest = hashlib.sha256(f"{seed}|{value}".encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return (integer + 1) / (2**64 + 1)


# ============================================================
# Analisi del dataset
# ============================================================

def get_classes(graph: Graph) -> set[URIRef]:
    return {
        c for c in graph.subjects(RDF.type, OWL.Class)
        if isinstance(c, URIRef)
    }


def get_object_properties(graph: Graph) -> set[URIRef]:
    return {
        p for p in graph.subjects(RDF.type, OWL.ObjectProperty)
        if isinstance(p, URIRef)
    }


def get_ordinary_individual_types(
    graph: Graph,
    classes: set[URIRef],
) -> dict[URIRef, set[URIRef]]:
    """
    Individui ordinari = soggetti di rdf:type che NON sono owl:Class.
    Manteniamo tutti i loro tipi diretti che puntano a classi OWL.
    """
    result: dict[URIRef, set[URIRef]] = defaultdict(set)

    for subject, cls in graph.subject_objects(RDF.type):
        if (
            isinstance(subject, URIRef)
            and cls in classes
            and subject not in classes
        ):
            result[subject].add(cls)

    return dict(result)


# ============================================================
# Selezione classi
# ============================================================

def build_class_dependencies(
    graph: Graph,
    classes: set[URIRef],
    include_subclass: bool,
    include_metamodeling: bool,
) -> dict[URIRef, set[URIRef]]:
    """
    Dipendenze necessarie per avere un prefisso semanticamente sensato.

    Se subclass è attivo:
      child -> parent

    Se metamodeling è attivo:
      classe-usata-come-individuo -> metaclasse
    """
    deps = {c: set() for c in classes}

    if include_subclass:
        for child, parent in graph.subject_objects(RDFS.subClassOf):
            if child in classes and parent in classes and child != parent:
                deps[child].add(parent)

    if include_metamodeling:
        for subject, meta in graph.subject_objects(RDF.type):
            if (
                subject in classes
                and meta in classes
                and subject != meta
            ):
                deps[subject].add(meta)

    return deps


def dependency_safe_order(
    classes: set[URIRef],
    dependencies: dict[URIRef, set[URIRef]],
    seed: int,
) -> list[URIRef]:
    """
    Ordinamento topologico deterministico:
    ogni dipendenza compare prima della classe che la usa.
    """
    children: dict[URIRef, set[URIRef]] = defaultdict(set)
    indegree = {c: 0 for c in classes}

    for cls, deps in dependencies.items():
        for dep in deps:
            if dep == cls:
                continue
            children[dep].add(cls)
            indegree[cls] += 1

    def key(c: URIRef):
        return (stable_hash(str(c), seed), str(c))

    available = sorted(
        [c for c in classes if indegree[c] == 0],
        key=key,
    )

    result = []

    while available:
        current = available.pop(0)
        result.append(current)

        for child in sorted(children.get(current, set()), key=key):
            indegree[child] -= 1
            if indegree[child] == 0:
                available.append(child)

        available.sort(key=key)

    if len(result) != len(classes):
        unresolved = classes - set(result)
        raise ValueError(
            "Class dependencies contain a cycle. "
            f"Unsortable classes: {len(unresolved)}."
        )

    return result



def dependency_closure(
    seed_classes: set[URIRef],
    dependencies: dict[URIRef, set[URIRef]],
) -> set[URIRef]:
    closure = set(seed_classes)
    stack = list(seed_classes)

    while stack:
        current = stack.pop()

        for dep in dependencies.get(current, set()):
            if dep not in closure:
                closure.add(dep)
                stack.append(dep)

    return closure


def select_classes_abox_aware(
    graph: Graph,
    all_classes: set[URIRef],
    dependencies: dict[URIRef, set[URIRef]],
    requested_class_count: int,
    requested_individual_count: int,
    seed: int,
) -> set[URIRef]:
    """
    Seleziona esattamente requested_class_count classi cercando di
    massimizzare il numero di individui ordinari coperti.

    È importante quando l'utente specifica contemporaneamente:
        numero classi + numero individui.

    La selezione:
    - resta chiusa rispetto alle dipendenze;
    - privilegia le classi con molti individui diretti;
    - usa un criterio deterministico;
    - dopo aver raggiunto una copertura sufficiente, riempie gli slot
      rimanenti con altre classi dependency-safe.
    """
    if requested_class_count > len(all_classes):
        raise ValueError(
            f"{requested_class_count} classes were requested, "
            f"but the FULL dataset contains only {len(all_classes)}."
        )

    individual_types = get_ordinary_individual_types(
        graph,
        all_classes,
    )

    members_by_class: dict[URIRef, set[URIRef]] = defaultdict(set)

    for individual, types in individual_types.items():
        for cls in types:
            members_by_class[cls].add(individual)

    selected: set[URIRef] = set()
    covered_individuals: set[URIRef] = set()

    # Cache delle closure per evitare di ricalcolarle continuamente.
    closure_cache = {
        cls: dependency_closure({cls}, dependencies)
        for cls in all_classes
    }

    # Greedy coverage-aware.
    while len(selected) < requested_class_count:
        best = None

        for cls in all_classes - selected:
            closure = closure_cache[cls]
            additions = closure - selected

            if not additions:
                continue

            if len(selected) + len(additions) > requested_class_count:
                continue

            newly_covered = set()
            for added_cls in additions:
                newly_covered.update(
                    members_by_class.get(added_cls, set())
                )

            newly_covered -= covered_individuals

            # Se dobbiamo ancora coprire individui, privilegia utility/costo.
            if len(covered_individuals) < requested_individual_count:
                utility = len(newly_covered) / len(additions)
                score = (
                    utility,
                    len(newly_covered),
                    -len(additions),
                    stable_hash(str(cls), seed),
                )
            else:
                # Una volta raggiunta la copertura necessaria,
                # privilegia aggiunte piccole per arrivare esattamente
                # al numero di classi richiesto.
                score = (
                    0.0,
                    0,
                    -len(additions),
                    stable_hash(str(cls), seed),
                )

            if best is None or score > best[0]:
                best = (score, cls, additions)

        if best is None:
            break

        _, _, additions = best
        selected.update(additions)

        for added_cls in additions:
            covered_individuals.update(
                members_by_class.get(added_cls, set())
            )

        if len(selected) == requested_class_count:
            break

    # Se il greedy non è arrivato esattamente al target, prova a riempire
    # con classi le cui dipendenze sono già presenti.
    if len(selected) < requested_class_count:
        remaining = sorted(
            all_classes - selected,
            key=lambda c: (
                stable_hash(str(c), seed),
                str(c),
            ),
        )

        progress = True

        while (
            len(selected) < requested_class_count
            and progress
        ):
            progress = False

            for cls in remaining:
                if cls in selected:
                    continue

                deps = dependencies.get(cls, set())

                if deps.issubset(selected):
                    selected.add(cls)
                    covered_individuals.update(
                        members_by_class.get(cls, set())
                    )
                    progress = True

                    if len(selected) == requested_class_count:
                        break

    if len(selected) != requested_class_count:
        raise ValueError(
            "Unable to build a dependency-closed set of exactly "
            f"{requested_class_count} classes."
        )

    # Controllo finale chiusura.
    for cls in selected:
        missing = dependencies.get(cls, set()) - selected
        if missing:
            raise RuntimeError(
                f"Internal error: {cls} has missing dependencies."
            )

    if len(covered_individuals) < requested_individual_count:
        raise ValueError(
            f"With {requested_class_count} classes, the maximum number of "
            f"individuals covered by the current selection is "
            f"{len(covered_individuals)}, which is lower than the requested "
            f"{requested_individual_count}. "
            "Increase the number of classes or reduce the number of individuals."
        )

    return selected



def build_subclass_parents(
    graph: Graph,
    classes: set[URIRef],
) -> dict[URIRef, set[URIRef]]:
    parents = {cls: set() for cls in classes}

    for child, parent in graph.subject_objects(RDFS.subClassOf):
        if child in classes and parent in classes and child != parent:
            parents[child].add(parent)

    return parents


def longest_subclass_chain(
    graph: Graph,
    classes: set[URIRef],
) -> list[URIRef]:
    """
    Return one deepest subclass chain as:
        leaf -> ... -> root
    """
    parents = build_subclass_parents(graph, classes)
    memo: dict[URIRef, list[URIRef]] = {}

    def best_chain(node: URIRef, visiting: set[URIRef]) -> list[URIRef]:
        if node in memo:
            return memo[node]

        if node in visiting:
            return [node]

        visiting = set(visiting)
        visiting.add(node)

        node_parents = parents.get(node, set())

        if not node_parents:
            result = [node]
        else:
            candidates = []

            for parent in sorted(node_parents, key=str):
                if parent in visiting:
                    continue
                candidates.append(
                    [node] + best_chain(parent, visiting)
                )

            result = max(candidates, key=len) if candidates else [node]

        memo[node] = result
        return result

    return max(
        (best_chain(cls, set()) for cls in classes),
        key=len,
    )


def select_classes_tbox_oriented(
    graph: Graph,
    all_classes: set[URIRef],
    dependencies: dict[URIRef, set[URIRef]],
    requested_class_count: int,
    seed: int,
) -> set[URIRef]:
    """
    TBox/metamodeling-oriented class selection.

    It preserves:
    - dependency closure;
    - one deepest subclass chain;
    - deterministic nested-style selection.

    This matches the intended TBox scalability interpretation better
    than an ABox-coverage-oriented selection.
    """
    if requested_class_count > len(all_classes):
        raise ValueError(
            f"{requested_class_count} classes were requested, "
            f"but the FULL dataset contains only {len(all_classes)}."
        )

    deepest_chain = longest_subclass_chain(
        graph,
        all_classes,
    )

    preferred_core = dependency_closure(
        set(deepest_chain),
        dependencies,
    )

    if len(preferred_core) > requested_class_count:
        raise ValueError(
            "The hierarchy-preserving core requires "
            f"{len(preferred_core)} classes, which is larger than "
            f"the requested size ({requested_class_count})."
        )

    children: dict[URIRef, set[URIRef]] = defaultdict(set)
    indegree = {cls: 0 for cls in all_classes}

    for cls, deps in dependencies.items():
        for dep in deps:
            if dep == cls:
                continue

            children[dep].add(cls)
            indegree[cls] += 1

    def priority(cls: URIRef):
        return (
            0 if cls in preferred_core else 1,
            stable_hash(str(cls), seed),
            str(cls),
        )

    available = sorted(
        [
            cls
            for cls in all_classes
            if indegree[cls] == 0
        ],
        key=priority,
    )

    order: list[URIRef] = []

    while available:
        current = available.pop(0)
        order.append(current)

        for child in sorted(
            children.get(current, set()),
            key=priority,
        ):
            indegree[child] -= 1

            if indegree[child] == 0:
                available.append(child)

        available.sort(key=priority)

    if len(order) != len(all_classes):
        raise ValueError(
            "Class dependencies contain a cycle and the "
            "TBox-oriented selection cannot be built."
        )

    selected = set(order[:requested_class_count])

    # Final closure check.
    for cls in selected:
        missing = dependencies.get(cls, set()) - selected

        if missing:
            raise RuntimeError(
                f"Internal error: {cls} has missing dependencies."
            )

    return selected


# ============================================================
# Selezione individui
# ============================================================

def select_individuals(
    graph: Graph,
    all_classes: set[URIRef],
    selected_classes: set[URIRef],
    requested_count: int,
    seed: int,
) -> tuple[set[URIRef], dict[URIRef, set[URIRef]], Counter]:
    """
    Campionamento stratificato deterministico.

    Un individuo è eleggibile se ha almeno un rdf:type verso una delle
    classi selezionate. Per ogni individuo vengono poi mantenuti TUTTI
    i suoi rdf:type che puntano a classi selezionate.
    """
    all_types = get_ordinary_individual_types(graph, all_classes)

    eligible_types = {
        individual: (types & selected_classes)
        for individual, types in all_types.items()
        if types & selected_classes
    }

    if requested_count > len(eligible_types):
        raise ValueError(
            f"{requested_count} individuals were requested, but with "
            f"the {len(selected_classes)} selected classes only "
            f"{len(eligible_types)} eligible individuals are available."
        )

    if requested_count == 0:
        return set(), eligible_types, Counter()

    class_sizes = Counter()
    for types in eligible_types.values():
        for cls in types:
            class_sizes[cls] += 1

    primary = {}
    for individual, types in eligible_types.items():
        primary[individual] = min(
            types,
            key=lambda c: (class_sizes[c], str(c)),
        )

    strata: dict[URIRef, list[URIRef]] = defaultdict(list)
    for individual, stratum in primary.items():
        strata[stratum].append(individual)

    for stratum, members in strata.items():
        members.sort(
            key=lambda i: (
                deterministic_uniform(str(i), seed),
                str(i),
            )
        )

    # Un rappresentante per stratum finché c'è spazio.
    representative_candidates = [
        members[0]
        for stratum, members in sorted(
            strata.items(),
            key=lambda item: str(item[0]),
        )
        if members
    ]

    selected_order: list[URIRef] = []

    for individual in representative_candidates:
        if len(selected_order) >= requested_count:
            break
        selected_order.append(individual)

    already = set(selected_order)

    # Per il resto: weighted sampling deterministico.
    remaining = []

    stratum_sizes = Counter(primary.values())

    for individual in eligible_types:
        if individual in already:
            continue

        stratum = primary[individual]
        size = stratum_sizes[stratum]

        weight = 1.0 / math.sqrt(size)
        u = deterministic_uniform(str(individual), seed)
        score = -math.log(u) / weight

        remaining.append((score, str(individual), individual))

    remaining.sort(key=lambda row: (row[0], row[1]))

    for _, _, individual in remaining:
        if len(selected_order) >= requested_count:
            break
        selected_order.append(individual)

    return set(selected_order), eligible_types, stratum_sizes



def select_individuals_by_percentage(
    graph: Graph,
    all_classes: set[URIRef],
    selected_classes: set[URIRef],
    percentage: float,
    seed: int,
) -> tuple[
    set[URIRef],
    dict[URIRef, set[URIRef]],
    Counter,
    dict[URIRef, URIRef],
]:
    """
    Deterministic percentage sampling by PRIMARY STRATUM.

    Each ordinary individual is assigned to exactly one primary stratum:
    among its selected direct types, the rarest direct class is chosen.
    Ties are broken by IRI.

    For each populated stratum C:
        sample_size(C) = max(1, ceil(percentage * |C| / 100))

    The deterministic ordering inside each stratum ensures nesting:
        10% ⊆ 25% ⊆ 50% ⊆ 75% ⊆ 100%
    for the same ontology, selected classes, and seed.

    All rdf:type assertions of every selected individual that point to
    selected classes are retained later by filter_graph().
    """
    if percentage <= 0 or percentage > 100:
        raise ValueError(
            "Percentage must be greater than 0 and less than or equal to 100."
        )

    all_types = get_ordinary_individual_types(
        graph,
        all_classes,
    )

    eligible_types = {
        individual: (types & selected_classes)
        for individual, types in all_types.items()
        if types & selected_classes
    }

    if not eligible_types:
        return set(), {}, Counter(), {}

    direct_class_sizes = Counter()

    for types in eligible_types.values():
        for cls in types:
            direct_class_sizes[cls] += 1

    primary_stratum: dict[URIRef, URIRef] = {}

    for individual, types in eligible_types.items():
        primary_stratum[individual] = min(
            types,
            key=lambda cls: (
                direct_class_sizes[cls],
                str(cls),
            ),
        )

    members_by_stratum: dict[URIRef, list[URIRef]] = defaultdict(list)

    for individual, stratum in primary_stratum.items():
        members_by_stratum[stratum].append(individual)

    for stratum, members in members_by_stratum.items():
        members.sort(
            key=lambda individual: (
                deterministic_uniform(str(individual), seed),
                str(individual),
            )
        )

    selected: set[URIRef] = set()
    stratum_sizes = Counter()

    for stratum, members in members_by_stratum.items():
        stratum_sizes[stratum] = len(members)

        count = max(
            1,
            math.ceil(len(members) * percentage / 100.0),
        )

        selected.update(members[:count])

    return (
        selected,
        eligible_types,
        stratum_sizes,
        primary_stratum,
    )


# ============================================================
# Proprietà / feature
# ============================================================

PREDATION_PROPERTIES = {
    EX.predatorOf,
    EX.landPredatorOf,
    EX.aerialPredatorOf,
    EX.aquaticPredatorOf,
    EX.preyOf,
    EX.landPreyOf,
    EX.aerialPreyOf,
    EX.aquaticPreyOf,
}

TAXONOMIC_PROPERTIES = {
    EX.hasDirectParentTaxon,
    EX.hasDirectChildTaxon,
}

COEXISTS_PROPERTIES = {
    EX.coexistsWith,
}


def property_family_enabled(prop: URIRef, options: dict) -> bool:
    if prop in PREDATION_PROPERTIES:
        return options["include_predation_roles"]

    if prop in TAXONOMIC_PROPERTIES:
        return options["include_taxonomic_roles"]

    if prop in COEXISTS_PROPERTIES:
        return options["include_coexists_role"]

    return options["include_other_roles"]


def filter_graph(
    source: Graph,
    selected_classes: set[URIRef],
    selected_individuals: set[URIRef],
    all_classes: set[URIRef],
    all_object_properties: set[URIRef],
    options: dict,
) -> Graph:
    """
    Crea il benchmark parametrico finale.
    """
    target = Graph()

    for prefix, namespace in source.namespaces():
        target.bind(prefix, namespace)

    allowed_entities = selected_classes | selected_individuals

    for s, p, o in source:

        # ----------------------------------------------------
        # Class declarations
        # ----------------------------------------------------
        if p == RDF.type and o == OWL.Class:
            if s in selected_classes:
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # Object property declarations
        # ----------------------------------------------------
        if p == RDF.type and o == OWL.ObjectProperty:
            if (
                isinstance(s, URIRef)
                and property_family_enabled(s, options)
            ):
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # Property characteristics
        # ----------------------------------------------------
        if p == RDF.type and o == OWL.ReflexiveProperty:
            if (
                options["include_reflexive"]
                and property_family_enabled(s, options)
            ):
                target.add((s, p, o))
            continue

        if p == RDF.type and o == OWL.IrreflexiveProperty:
            if (
                options["include_irreflexive"]
                and property_family_enabled(s, options)
            ):
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # rdf:type verso classi: ABox o metamodeling
        # ----------------------------------------------------
        if p == RDF.type and o in all_classes:
            if s in all_classes:
                # metamodeling
                if (
                    options["include_metamodeling"]
                    and s in selected_classes
                    and o in selected_classes
                ):
                    target.add((s, p, o))

            else:
                # individuo ordinario
                if (
                    s in selected_individuals
                    and o in selected_classes
                ):
                    target.add((s, p, o))

            continue

        # ----------------------------------------------------
        # subclass
        # ----------------------------------------------------
        if p == RDFS.subClassOf:
            if (
                options["include_subclass"]
                and s in selected_classes
                and o in selected_classes
            ):
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # subproperty
        # ----------------------------------------------------
        if p == RDFS.subPropertyOf:
            if (
                options["include_subproperty"]
                and isinstance(s, URIRef)
                and isinstance(o, URIRef)
                and property_family_enabled(s, options)
                and property_family_enabled(o, options)
            ):
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # inverse
        # ----------------------------------------------------
        if p == OWL.inverseOf:
            if (
                options["include_inverse"]
                and isinstance(s, URIRef)
                and isinstance(o, URIRef)
                and property_family_enabled(s, options)
                and property_family_enabled(o, options)
            ):
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # class disjointness
        # ----------------------------------------------------
        if p == OWL.disjointWith:
            if (
                options["include_class_disjointness"]
                and s in selected_classes
                and o in selected_classes
            ):
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # role disjointness
        # ----------------------------------------------------
        if p == OWL.propertyDisjointWith:
            if (
                options["include_role_disjointness"]
                and isinstance(s, URIRef)
                and isinstance(o, URIRef)
                and property_family_enabled(s, options)
                and property_family_enabled(o, options)
            ):
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # domain / range
        # ----------------------------------------------------
        if p in (RDFS.domain, RDFS.range):
            # Domain and range are always included when their property
            # and referenced class are part of the selected benchmark.
            if isinstance(s, URIRef) and not property_family_enabled(s, options):
                continue

            if o in all_classes and o not in selected_classes:
                continue

            target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # label
        # ----------------------------------------------------
        if p == RDFS.label:
            if (
                s in selected_classes
                or s in selected_individuals
                or (
                    s in all_object_properties
                    and property_family_enabled(s, options)
                )
            ):
                target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # Role assertions
        # ----------------------------------------------------
        if p in all_object_properties:
            if not property_family_enabled(p, options):
                continue

            # Se un endpoint è una classe del dataset originale,
            # deve essere fra le classi selezionate.
            if s in all_classes and s not in selected_classes:
                continue
            if o in all_classes and o not in selected_classes:
                continue

            # Se un endpoint è un individuo ordinario, deve essere selezionato.
            if (
                isinstance(s, URIRef)
                and s not in all_classes
                and any(source.objects(s, RDF.type))
                and s not in selected_individuals
            ):
                continue

            if (
                isinstance(o, URIRef)
                and o not in all_classes
                and any(source.objects(o, RDF.type))
                and o not in selected_individuals
            ):
                continue

            target.add((s, p, o))
            continue

        # ----------------------------------------------------
        # Altre triple
        # Manteniamo soltanto quelle che non coinvolgono classi
        # o individui esclusi.
        # ----------------------------------------------------
        if s in all_classes and s not in selected_classes:
            continue
        if o in all_classes and o not in selected_classes:
            continue

        if s in allowed_entities or o in allowed_entities:
            target.add((s, p, o))

    return target


# ============================================================
# Statistiche output
# ============================================================

def benchmark_stats(
    graph: Graph,
    selected_classes: set[URIRef],
    selected_individuals: set[URIRef],
) -> dict:
    return {
        "rdf_triples": len(graph),
        "classes": len(selected_classes),
        "ordinary_individuals": len(selected_individuals),
        "ordinary_type_assertions": sum(
            1
            for s, o in graph.subject_objects(RDF.type)
            if s in selected_individuals and o in selected_classes
        ),
        "metamodeling_assertions": sum(
            1
            for s, o in graph.subject_objects(RDF.type)
            if s in selected_classes and o in selected_classes
        ),
        "subclass_axioms": sum(1 for _ in graph.triples((None, RDFS.subClassOf, None))),
        "subproperty_axioms": sum(1 for _ in graph.triples((None, RDFS.subPropertyOf, None))),
        "inverse_axioms": sum(1 for _ in graph.triples((None, OWL.inverseOf, None))),
        "class_disjointness_axioms": sum(1 for _ in graph.triples((None, OWL.disjointWith, None))),
        "role_disjointness_axioms": sum(1 for _ in graph.triples((None, OWL.propertyDisjointWith, None))),
        "domain_axioms": sum(1 for _ in graph.triples((None, RDFS.domain, None))),
        "range_axioms": sum(1 for _ in graph.triples((None, RDFS.range, None))),
        "reflexive_properties": sum(
            1 for _ in graph.triples((None, RDF.type, OWL.ReflexiveProperty))
        ),
        "irreflexive_properties": sum(
            1 for _ in graph.triples((None, RDF.type, OWL.IrreflexiveProperty))
        ),
    }


# ============================================================
# Analisi descrittiva (solo fatti espliciti, non fatti inferiti)
# ============================================================

FEATURE_LABELS = {
    "include_subclass": "Subclass axioms",
    "include_metamodeling": "Class metamodeling",
    "include_subproperty": "Subproperty axioms",
    "include_inverse": "Inverse properties",
    "include_class_disjointness": "Class disjointness",
    "include_role_disjointness": "Role disjointness",
    "include_reflexive": "Reflexive properties",
    "include_irreflexive": "Irreflexive properties",
    "include_predation_roles": "Predation roles",
    "include_taxonomic_roles": "Taxonomic roles",
    "include_coexists_role": "Coexistence role",
    "include_other_roles": "Other roles",
}


def role_family_name(prop: URIRef) -> str:
    if prop in PREDATION_PROPERTIES:
        return "predation"
    if prop in TAXONOMIC_PROPERTIES:
        return "taxonomic"
    if prop in COEXISTS_PROPERTIES:
        return "coexistence"
    return "other"


def ontology_semantic_profile(graph: Graph) -> dict:
    """Profile of explicit RDF facts, without reasoning or OWL inference.

    All values are JSON serializable. The definition of an ordinary individual
    matches the existing generator's sampling policy.
    """
    classes = get_classes(graph)
    properties = get_object_properties(graph)
    individuals = get_ordinary_individual_types(graph, classes)
    base = benchmark_stats(graph, classes, set(individuals))

    role_counts = Counter()
    for _, prop, _ in graph:
        if prop in properties:
            role_counts[prop] += 1

    metaclass_members = {
        subject for subject, typ in graph.subject_objects(RDF.type)
        if subject in classes and typ in classes
    }
    metaclasses = {
        typ for subject, typ in graph.subject_objects(RDF.type)
        if subject in classes and typ in classes
    }
    properties_as_individuals = {
        subject for subject, typ in graph.subject_objects(RDF.type)
        if subject in properties and typ in classes
    }
    prop_details = []
    for prop in sorted(properties, key=str):
        prop_details.append({
            "iri": str(prop),
            "family": role_family_name(prop),
            "assertions": role_counts[prop],
            "domains": sorted(str(o) for o in graph.objects(prop, RDFS.domain)),
            "ranges": sorted(str(o) for o in graph.objects(prop, RDFS.range)),
        })

    families = {name: {"properties": 0, "assertions": 0}
                for name in ("predation", "taxonomic", "coexistence", "other")}
    for prop in prop_details:
        family = families[prop["family"]]
        family["properties"] += 1
        family["assertions"] += prop["assertions"]

    counts = {
        **base,
        "object_properties": len(properties),
        "role_assertions": sum(role_counts.values()),
        "properties_with_assertions": sum(bool(n) for n in role_counts.values()),
        "classes_used_as_individuals": len(metaclass_members),
        "metaclasses": len(metaclasses),
        "properties_used_as_individuals": len(properties_as_individuals),
    }
    return {
        "counting_policy": (
            "Explicit RDF triples only; no entailment/materialization. "
            "Individuals follow the benchmark generator's direct rdf:type policy."
        ),
        "statistics": counts,
        "role_families": families,
        "object_property_details": prop_details,
    }


def format_ontology_overview(profile: dict) -> str:
    """Human-readable FULL ontology overview shown before generation."""
    d = profile["statistics"]
    lines = [
        "FULL ONTOLOGY — explicit RDF facts (before sampling)",
        f"RDF triples: {d['rdf_triples']:,}",
        f"OWL classes: {d['classes']:,}  |  Ordinary typed individuals: {d['ordinary_individuals']:,}",
        f"Class assertions: {d['ordinary_type_assertions']:,}  |  Class metamodeling: {d['metamodeling_assertions']:,}",
        f"Classes used as individuals: {d['classes_used_as_individuals']:,}  |  Metaclasses: {d['metaclasses']:,}",
        f"Object properties: {d['object_properties']:,}  |  Explicit role assertions: {d['role_assertions']:,}",
        f"SubClassOf: {d['subclass_axioms']:,}  |  SubPropertyOf: {d['subproperty_axioms']:,}  |  Inverse: {d['inverse_axioms']:,}",
        f"Domain: {d['domain_axioms']:,}  |  Range: {d['range_axioms']:,}",
        f"Class/role disjointness: {d['class_disjointness_axioms']:,} / {d['role_disjointness_axioms']:,}",
        f"Reflexive / irreflexive declarations: {d['reflexive_properties']:,} / {d['irreflexive_properties']:,}",
        "Role families (properties / assertions): " + ", ".join(
            f"{k}: {v['properties']} / {v['assertions']}"
            for k, v in profile["role_families"].items()
        ),
        "Most populated roles: " + (
            ", ".join(
                f"{entry['iri'].rsplit('/', 1)[-1]} ({entry['assertions']})"
                for entry in sorted(profile["object_property_details"],
                                    key=lambda x: (-x["assertions"], x["iri"]))[:6]
                if entry["assertions"]
            ) or "none"
        ),
        "NOTE: Counts reflect source assertions, not reasoner-inferred facts.",
    ]
    return "\n".join(lines)


def make_semantic_report(
    *,
    name: str,
    input_path: Path,
    owl_path: Path,
    config: dict,
    input_profile: dict,
    output_profile: dict,
) -> str:
    """Readable, explicit summary for reproducibility and experiment auditing."""
    counts = output_profile["statistics"]
    lines = [
        "PARAMETRIC OWL BENCHMARK — SEMANTIC REPORT",
        "=" * 66,
        f"Benchmark: {name}",
        f"Source: {portable_config_path(input_path)}",
        f"Output: {portable_config_path(owl_path)}",
        f"Seed: {config['seed']}",
        f"Class selection: {config['class_selection_mode']}",
        f"Individual sampling: {config['individual_sampling_mode']}",
        f"Requested classes: {config['requested_classes']}",
        f"Requested sampling percentage: {config['requested_percentage_per_primary_stratum']}",
        f"Requested fixed individuals: {config['requested_fixed_individuals']}",
        "",
        "ENABLED FEATURES (configuration — not necessarily present in output)",
        "-" * 66,
    ]
    for key, enabled in config["features"].items():
        lines.append(f"{FEATURE_LABELS.get(key, key)}: {'ON' if enabled else 'OFF'}")

    lines.extend(["", "FULL SOURCE ONTOLOGY", "-" * 66])
    for key, value in input_profile["statistics"].items():
        lines.append(f"{key}: {value}")
    lines.extend(["", "GENERATED BENCHMARK — ACTUAL EXPLICIT COUNTS", "-" * 66])
    for key, value in counts.items():
        lines.append(f"{key}: {value}")
    lines.extend(["", "ROLE FAMILIES (declared properties / explicit assertions)", "-" * 66])
    for family, vals in output_profile["role_families"].items():
        lines.append(f"{family}: {vals['properties']} properties; {vals['assertions']} assertions")
    lines.extend(["", "DECLARED OBJECT PROPERTIES", "-" * 66])
    for prop in output_profile["object_property_details"]:
        lines.append(f"{prop['iri']}  [{prop['family']}]  assertions={prop['assertions']}")
        if prop["domains"]:
            lines.append("  domain: " + ", ".join(prop["domains"]))
        if prop["ranges"]:
            lines.append("  range: " + ", ".join(prop["ranges"]))
    lines.extend([
        "", "INTERPRETATION NOTES", "-" * 66,
        "Every count concerns explicit RDF facts; inferred facts are not included.",
        "A feature can be ON but have zero corresponding statements in the generated benchmark.",
        "Role assertions count only predicates explicitly declared as owl:ObjectProperty.",
        "Ordinary individuals follow the generator's existing sampling definition.",
    ])
    return "\n".join(lines) + "\n"


# ============================================================
# GUI
# ============================================================

class BenchmarkGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        self.geometry("920x760")
        self.minsize(820, 620)

        self.log_queue = queue.Queue()

        self.input_var = tk.StringVar(
            value="ontology/animal_taxonomy_ontology_complete.owl"
        )
        self.output_dir_var = tk.StringVar(
            value="generated_benchmarks"
        )
        self.name_var = tk.StringVar(
            value="benchmark_custom"
        )

        self.instances_var = tk.StringVar(value="10000")
        self.classes_var = tk.StringVar(value="300")
        self.seed_var = tk.StringVar(value="42")
        self.overwrite_var = tk.BooleanVar(value=False)

        # Individual sampling.
        self.sampling_mode_var = tk.StringVar(value="percentage")
        self.percentage_var = tk.StringVar(value="25")

        # Class selection strategy. Presets set this automatically.
        # It remains editable through the dropdown in the GUI.
        self.class_selection_mode_var = tk.StringVar(value="abox_aware")

        # Feature semantiche
        self.feature_vars = {
            "include_subclass": tk.BooleanVar(value=True),
            "include_metamodeling": tk.BooleanVar(value=True),
            "include_subproperty": tk.BooleanVar(value=True),
            "include_inverse": tk.BooleanVar(value=True),
            "include_class_disjointness": tk.BooleanVar(value=True),
            "include_role_disjointness": tk.BooleanVar(value=True),
            "include_reflexive": tk.BooleanVar(value=True),
            "include_irreflexive": tk.BooleanVar(value=True),
        }

        # Famiglie di ruoli
        self.role_vars = {
            "include_predation_roles": tk.BooleanVar(value=True),
            "include_taxonomic_roles": tk.BooleanVar(value=True),
            "include_coexists_role": tk.BooleanVar(value=True),
            "include_other_roles": tk.BooleanVar(value=True),
        }

        self.status_var = tk.StringVar(value="Ready.")
        self.dataset_info_var = tk.StringVar(
            value="Source ontology not analyzed yet."
        )
        self.progress_var = tk.DoubleVar(value=0)
        self.phase_var = tk.StringVar(value="Not started — progress is shown by completed phases")
        self.selected_features_preview_var = tk.StringVar(value="")
        self._analysis_running = False
        self._generation_running = False
        self._last_analyzed_path = None
        self._last_analyzed_signature = None
        self._cached_ontology_profile = None

        self._build_ui()
        for variable in (*self.feature_vars.values(), *self.role_vars.values()):
            variable.trace_add("write", self._update_feature_preview)
        self._update_feature_preview()
        self.input_var.trace_add("write", self._invalidate_ontology_preview)
        self.after(100, self._drain_log_queue)
        try:
            if resolve_user_path(self.input_var.get()).is_file():
                self.after(250, self._analyze_dataset)
        except ValueError:
            pass

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def _build_ui(self):
        # Scrollable root area so the whole interface remains accessible
        # even on screens with limited vertical resolution.
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(
            container,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(
            container,
            orient="vertical",
            command=canvas.yview,
        )

        canvas.configure(
            yscrollcommand=scrollbar.set
        )

        scrollbar.pack(
            side="right",
            fill="y",
        )
        canvas.pack(
            side="left",
            fill="both",
            expand=True,
        )

        outer = ttk.Frame(
            canvas,
            padding=14,
        )

        canvas_window = canvas.create_window(
            (0, 0),
            window=outer,
            anchor="nw",
        )

        def update_scroll_region(event=None):
            canvas.configure(
                scrollregion=canvas.bbox("all")
            )

        def resize_inner_frame(event):
            canvas.itemconfigure(
                canvas_window,
                width=event.width,
            )

        outer.bind(
            "<Configure>",
            update_scroll_region,
        )
        canvas.bind(
            "<Configure>",
            resize_inner_frame,
        )

        def on_mousewheel(event):
            # Windows/macOS mouse wheel.
            if event.delta:
                canvas.yview_scroll(
                    int(-1 * (event.delta / 120)),
                    "units",
                )

        def on_linux_scroll_up(event):
            canvas.yview_scroll(-1, "units")

        def on_linux_scroll_down(event):
            canvas.yview_scroll(1, "units")

        canvas.bind_all(
            "<MouseWheel>",
            on_mousewheel,
        )
        canvas.bind_all(
            "<Button-4>",
            on_linux_scroll_up,
        )
        canvas.bind_all(
            "<Button-5>",
            on_linux_scroll_down,
        )

        ttk.Label(
            outer,
            text="Parametric Benchmark Generator",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 10))

        files = ttk.LabelFrame(
            outer,
            text="Input / output",
            padding=10,
        )
        files.pack(fill="x", pady=(0, 10))

        ttk.Label(files, text="FULL ontology:").grid(
            row=0, column=0, sticky="w", pady=4
        )
        ttk.Entry(
            files,
            textvariable=self.input_var,
        ).grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Button(
            files,
            text="Browse...",
            command=self._browse_input,
        ).grid(row=0, column=2, padx=(8, 0))

        ttk.Label(files, text="Output folder:").grid(
            row=1, column=0, sticky="w", pady=4
        )
        ttk.Entry(
            files,
            textvariable=self.output_dir_var,
        ).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Button(
            files,
            text="Browse...",
            command=self._browse_output,
        ).grid(row=1, column=2, padx=(8, 0))

        ttk.Label(files, text="Benchmark name:").grid(
            row=2, column=0, sticky="w", pady=4
        )
        ttk.Entry(
            files,
            textvariable=self.name_var,
        ).grid(row=2, column=1, sticky="ew", pady=4)

        self.analyze_button = ttk.Button(
            files,
            text="Analyze source ontology",
            command=self._analyze_dataset,
        )
        self.analyze_button.grid(row=2, column=2, padx=(8, 0))

        files.columnconfigure(1, weight=1)

        ttk.Label(
            files,
            textvariable=self.dataset_info_var,
        ).grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(8, 0),
        )

        overview = ttk.LabelFrame(
            outer,
            text="Source ontology statistics — before benchmark generation",
            padding=10,
        )
        overview.pack(fill="x", pady=(0, 10))
        self.ontology_overview = tk.Text(
            overview,
            height=11,
            font=("Consolas", 9),
            wrap="word",
            state="disabled",
        )
        overview_scrollbar = ttk.Scrollbar(overview, command=self.ontology_overview.yview)
        self.ontology_overview.configure(yscrollcommand=overview_scrollbar.set)
        self.ontology_overview.pack(side="left", fill="both", expand=True)
        overview_scrollbar.pack(side="right", fill="y")
        self._set_overview_text("Click 'Analyze source ontology' to see statistics before generation.")

        preview = ttk.LabelFrame(outer, text="Selected semantic configuration (preview)", padding=10)
        preview.pack(fill="x", pady=(0, 10))
        ttk.Label(
            preview,
            textvariable=self.selected_features_preview_var,
            wraplength=850,
            justify="left",
        ).pack(fill="x")

        size = ttk.LabelFrame(
            outer,
            text="Benchmark Size",
            padding=10,
        )
        size.pack(fill="x", pady=(0, 10))

        ttk.Label(size, text="Number of classes:").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Entry(
            size,
            width=12,
            textvariable=self.classes_var,
        ).grid(row=0, column=1, sticky="w", padx=(6, 24))

        ttk.Label(size, text="Class selection:").grid(
            row=0, column=2, sticky="w"
        )

        class_strategy = ttk.Combobox(
            size,
            width=18,
            state="readonly",
            textvariable=self.class_selection_mode_var,
            values=("abox_aware", "tbox_oriented"),
        )
        class_strategy.grid(
            row=0, column=3, sticky="w", padx=(6, 24)
        )

        ttk.Label(size, text="Seed:").grid(
            row=0, column=4, sticky="w"
        )
        ttk.Entry(
            size,
            width=10,
            textvariable=self.seed_var,
        ).grid(row=0, column=5, sticky="w", padx=(6, 0))

        sampling = ttk.LabelFrame(
            outer,
            text="Individual Sampling",
            padding=10,
        )
        sampling.pack(fill="x", pady=(0, 10))

        ttk.Radiobutton(
            sampling,
            text="Percentage per primary stratum",
            variable=self.sampling_mode_var,
            value="percentage",
        ).grid(row=0, column=0, sticky="w", pady=3)

        ttk.Label(
            sampling,
            text="Percentage:",
        ).grid(row=0, column=1, sticky="e", padx=(12, 4))

        ttk.Entry(
            sampling,
            width=8,
            textvariable=self.percentage_var,
        ).grid(row=0, column=2, sticky="w")

        ttk.Label(
            sampling,
            text="%",
        ).grid(row=0, column=3, sticky="w", padx=(3, 14))

        for index, percentage in enumerate((10, 25, 50, 75, 100)):
            ttk.Button(
                sampling,
                text=f"{percentage}%",
                command=lambda value=percentage: self._set_percentage(value),
                width=6,
            ).grid(
                row=0,
                column=4 + index,
                padx=2,
                pady=3,
            )

        ttk.Radiobutton(
            sampling,
            text="Fixed total number of individuals",
            variable=self.sampling_mode_var,
            value="fixed",
        ).grid(row=1, column=0, sticky="w", pady=3)

        ttk.Label(
            sampling,
            text="Individuals:",
        ).grid(row=1, column=1, sticky="e", padx=(12, 4))

        ttk.Entry(
            sampling,
            width=12,
            textvariable=self.instances_var,
        ).grid(row=1, column=2, columnspan=2, sticky="w")

        ttk.Radiobutton(
            sampling,
            text="All eligible individuals",
            variable=self.sampling_mode_var,
            value="all",
        ).grid(row=2, column=0, sticky="w", pady=3)

        ttk.Radiobutton(
            sampling,
            text="Classes only (keep metamodeling)",
            variable=self.sampling_mode_var,
            value="classes_only",
        ).grid(row=3, column=0, sticky="w", pady=3)

        ttk.Label(
            sampling,
            text=(
                "Classes-only mode removes ordinary individuals but keeps "
                "class-as-individual metamodeling assertions."
            ),
        ).grid(
            row=4,
            column=0,
            columnspan=9,
            sticky="w",
            pady=(7, 0),
        )

        ttk.Label(
            sampling,
            text=(
                "Percentage sampling uses one primary stratum per individual "
                "and is deterministic/nested for a fixed seed."
            ),
        ).grid(
            row=5,
            column=0,
            columnspan=9,
            sticky="w",
            pady=(4, 0),
        )

        presets = ttk.LabelFrame(
            outer,
            text="Benchmark Presets",
            padding=10,
        )
        presets.pack(fill="x", pady=(0, 10))

        ttk.Label(
            presets,
            text="ABox scalability:",
        ).grid(row=0, column=0, sticky="w", padx=(0, 10), pady=3)

        for index, preset_name in enumerate(("A1", "A2", "A3", "A4", "A5")):
            label = {
                "A1": "A1 · 10%",
                "A2": "A2 · 25%",
                "A3": "A3 · 50%",
                "A4": "A4 · 75%",
                "A5": "A5 · 100%",
            }[preset_name]

            ttk.Button(
                presets,
                text=label,
                command=lambda name=preset_name: self._apply_abox_preset(name),
            ).grid(
                row=0,
                column=index + 1,
                padx=3,
                pady=3,
                sticky="ew",
            )

        ttk.Label(
            presets,
            text="TBox / meta scalability:",
        ).grid(row=1, column=0, sticky="w", padx=(0, 10), pady=3)

        for index, preset_name in enumerate(("T1", "T2", "T3", "T4")):
            label = {
                "T1": "T1 · 150",
                "T2": "T2 · 300",
                "T3": "T3 · 450",
                "T4": "T4 · FULL",
            }[preset_name]

            ttk.Button(
                presets,
                text=label,
                command=lambda name=preset_name: self._apply_tbox_preset(name),
            ).grid(
                row=1,
                column=index + 1,
                padx=3,
                pady=3,
                sticky="ew",
            )

        ttk.Button(
            presets,
            text="Full semantics",
            command=self._enable_full_semantics,
        ).grid(
            row=1,
            column=5,
            padx=3,
            pady=3,
            sticky="ew",
        )

        ttk.Label(
            presets,
            text=(
                "ABox presets use 10/25/50/75/100% per primary stratum. "
                "TBox/meta presets use 25% per primary stratum. "
                "All presets restore seed 42 and full semantics."
            ),
        ).grid(
            row=2,
            column=0,
            columnspan=6,
            sticky="w",
            pady=(7, 0),
        )

        for col in range(1, 6):
            presets.columnconfigure(col, weight=1)

        features = ttk.LabelFrame(
            outer,
            text="Semantic Features to Include",
            padding=10,
        )
        features.pack(fill="x", pady=(0, 10))

        feature_labels = [
            ("include_subclass", "rdfs:subClassOf"),
            ("include_metamodeling", "Metamodeling (classes as individuals)"),
            ("include_subproperty", "rdfs:subPropertyOf"),
            ("include_inverse", "owl:inverseOf"),
            ("include_class_disjointness", "owl:disjointWith"),
            ("include_role_disjointness", "owl:propertyDisjointWith"),
            ("include_reflexive", "owl:ReflexiveProperty"),
            ("include_irreflexive", "owl:IrreflexiveProperty"),
        ]

        for index, (key, label) in enumerate(feature_labels):
            row = index // 3
            col = index % 3

            ttk.Checkbutton(
                features,
                text=label,
                variable=self.feature_vars[key],
            ).grid(
                row=row,
                column=col,
                sticky="w",
                padx=(0, 24),
                pady=4,
            )

        roles = ttk.LabelFrame(
            outer,
            text="Role Families to Include",
            padding=10,
        )
        roles.pack(fill="x", pady=(0, 10))

        role_labels = [
            ("include_predation_roles", "Predator / prey"),
            ("include_taxonomic_roles", "hasDirectParent/ChildTaxon"),
            ("include_coexists_role", "coexistsWith"),
            ("include_other_roles", "Other roles"),
        ]

        for index, (key, label) in enumerate(role_labels):
            ttk.Checkbutton(
                roles,
                text=label,
                variable=self.role_vars[key],
            ).grid(
                row=0,
                column=index,
                sticky="w",
                padx=(0, 24),
                pady=4,
            )

        options = ttk.Frame(outer)
        options.pack(fill="x", pady=(0, 10))

        ttk.Checkbutton(
            options,
            text="Overwrite files with the same name",
            variable=self.overwrite_var,
        ).pack(side="left")

        self.generate_button = ttk.Button(
            options,
            text="Generate benchmark",
            command=self._start_generation,
        )
        self.generate_button.pack(side="right")

        ttk.Label(
            options,
            textvariable=self.status_var,
        ).pack(side="right", padx=(0, 12))

        progress_frame = ttk.LabelFrame(outer, text="Generation progress (completed phases)", padding=10)
        progress_frame.pack(fill="x", pady=(0, 10))
        ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        ).pack(fill="x")
        ttk.Label(progress_frame, textvariable=self.phase_var).pack(anchor="w", pady=(4, 0))

        logframe = ttk.LabelFrame(
            outer,
            text="Log",
            padding=8,
        )
        logframe.pack(fill="both", expand=True)

        self.log = tk.Text(
            logframe,
            state="disabled",
            wrap="word",
            font=("Consolas", 9),
        )
        self.log.pack(
            side="left",
            fill="both",
            expand=True,
        )

        scroll = ttk.Scrollbar(
            logframe,
            orient="vertical",
            command=self.log.yview,
        )
        scroll.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scroll.set)

    # --------------------------------------------------------
    # Presets
    # --------------------------------------------------------

    def _set_percentage(self, value: int):
        self.sampling_mode_var.set("percentage")
        self.percentage_var.set(str(value))
        self.status_var.set(f"{value}% sampling selected.")

    def _enable_full_semantics(self):
        """Enable all optional semantic features and all role families."""
        for variable in self.feature_vars.values():
            variable.set(True)

        for variable in self.role_vars.values():
            variable.set(True)

        self.seed_var.set("42")
        self.status_var.set("Full semantics enabled.")

    def _read_full_sizes(self) -> tuple[int, int]:
        """
        Read the current FULL ontology and return:
            (number of OWL classes, number of ordinary individuals)
        """
        path = resolve_user_path(self.input_var.get())

        if not path.exists():
            raise FileNotFoundError(
                f"FULL ontology not found: {path.resolve()}"
            )

        signature = self._file_signature(path)
        if (self._last_analyzed_signature == signature and
                self._cached_ontology_profile is not None):
            profile = self._cached_ontology_profile
        else:
            graph = Graph()
            graph.parse(path)
            profile = ontology_semantic_profile(graph)
            self._accept_ontology_profile(path, profile, signature)

        d = profile["statistics"]
        return d["classes"], d["ordinary_individuals"]

    def _apply_abox_preset(self, preset_name: str):
        """
        ABox scalability presets:
            A1 = 10%
            A2 = 25%
            A3 = 50%
            A4 = 75%
            A5 = 100%

        All FULL classes are retained.
        Sampling is performed per primary stratum.
        """
        try:
            full_classes, _ = self._read_full_sizes()

            percentage = ABOX_PRESETS[preset_name]

            self.classes_var.set(str(full_classes))
            self.class_selection_mode_var.set("abox_aware")
            self.sampling_mode_var.set("percentage")
            self.percentage_var.set(str(percentage))
            self.name_var.set(f"{preset_name}_abox")
            self._enable_full_semantics()

            self.status_var.set(
                f"{preset_name} preset loaded ({percentage}%)."
            )

        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Unable to apply {preset_name} preset:\\n{exc}",
            )

    def _apply_tbox_preset(self, preset_name: str):
        """
        TBox/metamodeling scalability presets:
            T1 = 150 classes
            T2 = 300 classes
            T3 = 450 classes
            T4 = FULL classes

        Ordinary individuals are sampled at a constant 25% per primary
        stratum, so the TBox size grows without an uncontrolled ABox jump.
        """
        try:
            full_classes, _ = self._read_full_sizes()

            requested = TBOX_PRESETS[preset_name]
            class_count = (
                full_classes
                if requested is None
                else requested
            )

            if class_count > full_classes:
                raise ValueError(
                    f"{preset_name} requires {class_count:,} classes, "
                    f"but this ontology contains only {full_classes:,}."
                )

            self.classes_var.set(str(class_count))
            self.class_selection_mode_var.set("tbox_oriented")
            self.sampling_mode_var.set("percentage")
            self.percentage_var.set(
                str(DEFAULT_TBOX_INDIVIDUAL_PERCENTAGE)
            )
            self.name_var.set(f"{preset_name}_tbox_meta")
            self._enable_full_semantics()

            self.status_var.set(
                f"{preset_name} preset loaded "
                f"({DEFAULT_TBOX_INDIVIDUAL_PERCENTAGE}% individuals)."
            )

        except Exception as exc:
            messagebox.showerror(
                APP_TITLE,
                f"Unable to apply {preset_name} preset:\\n{exc}",
            )

    # --------------------------------------------------------
    # Browse / analyze
    # --------------------------------------------------------

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Select FULL ontology",
            filetypes=[
                ("OWL/RDF", "*.owl *.rdf *.xml"),
                ("All files", "*.*"),
            ],
        )
        if path:
            self.input_var.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(
            title="Select output folder"
        )
        if path:
            self.output_dir_var.set(path)

    @staticmethod
    def _file_signature(path: Path):
        resolved = path.resolve()
        stat = resolved.stat()
        return str(resolved), stat.st_size, stat.st_mtime_ns

    def _set_overview_text(self, content: str):
        self.ontology_overview.configure(state="normal")
        self.ontology_overview.delete("1.0", "end")
        self.ontology_overview.insert("1.0", content)
        self.ontology_overview.configure(state="disabled")

    def _invalidate_ontology_preview(self, *args):
        self._cached_ontology_profile = None
        self._last_analyzed_signature = None
        self._last_analyzed_path = None
        self.dataset_info_var.set("Source ontology changed. Analyze again.")
        self._set_overview_text("Source changed: click 'Analyze source ontology'.")

    def _update_feature_preview(self, *args):
        enabled = [FEATURE_LABELS.get(k, k) for k, v in self._read_options().items() if v]
        disabled = [FEATURE_LABELS.get(k, k) for k, v in self._read_options().items() if not v]
        self.selected_features_preview_var.set(
            "ENABLED: " + (", ".join(enabled) or "none") +
            "\nDISABLED: " + (", ".join(disabled) or "none") +
            "\nThe generated report will also show which axioms and facts are actually present."
        )

    def _accept_ontology_profile(self, path: Path, profile: dict, signature):
        self._last_analyzed_path = str(path.resolve())
        self._last_analyzed_signature = signature
        self._cached_ontology_profile = profile
        d = profile["statistics"]
        self.dataset_info_var.set(
            f"FULL: {d['rdf_triples']:,} triples | {d['classes']:,} classes | "
            f"{d['ordinary_individuals']:,} individuals | "
            f"{d['object_properties']:,} object properties"
        )
        self._set_overview_text(format_ontology_overview(profile))

    def _analyze_dataset(self):
        if self._analysis_running or self._generation_running:
            return
        path = resolve_user_path(self.input_var.get())
        if not path.is_file():
            messagebox.showerror(APP_TITLE, f"Source ontology not found:\n{path}")
            return
        self._analysis_running = True
        self.analyze_button.configure(state="disabled")
        self.generate_button.configure(state="disabled")
        self.dataset_info_var.set("Analyzing source ontology…")
        threading.Thread(target=self._analyze_worker, args=(path,), daemon=True).start()

    def _analyze_worker(self, path: Path):
        try:
            signature = self._file_signature(path)
            graph = Graph()
            graph.parse(path)
            profile = ontology_semantic_profile(graph)
            self.log_queue.put(("analysis_ready", path, signature, profile))
        except Exception as exc:
            self.log_queue.put(("analysis_error", str(exc)))

    # --------------------------------------------------------
    # Parametri
    # --------------------------------------------------------

    @staticmethod
    def _int_value(
        value: str,
        name: str,
        allow_zero: bool = False,
    ) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError(
                f"{name} must be an integer."
            ) from exc

        minimum = 0 if allow_zero else 1

        if number < minimum:
            raise ValueError(
                f"{name} must be >= {minimum}."
            )

        return number

    def _read_options(self) -> dict:
        options = {
            key: variable.get()
            for key, variable in self.feature_vars.items()
        }

        options.update({
            key: variable.get()
            for key, variable in self.role_vars.items()
        })

        return options

    # --------------------------------------------------------
    # Generation
    # --------------------------------------------------------

    def _snapshot_generation_settings(self) -> dict:
        """Read all Tk variables on the main thread, never in the worker."""
        return {
            "input_path": self.input_var.get().strip(),
            "output_dir": self.output_dir_var.get().strip(),
            "name": self.name_var.get().strip(),
            "classes": self.classes_var.get().strip(),
            "sampling_mode": self.sampling_mode_var.get().strip(),
            "class_selection_mode": self.class_selection_mode_var.get().strip(),
            "percentage": self.percentage_var.get().strip(),
            "instances": self.instances_var.get().strip(),
            "seed": self.seed_var.get().strip(),
            "overwrite": self.overwrite_var.get(),
            "options": self._read_options(),
        }

    def _set_phase(self, percent: int, label: str):
        """Completion of named phases; not a prediction of elapsed time."""
        self.log_queue.put(("progress", percent, label))

    def _start_generation(self):
        if self._analysis_running or self._generation_running:
            return
        settings = self._snapshot_generation_settings()
        self._generation_running = True
        self.generate_button.configure(state="disabled")
        self.analyze_button.configure(state="disabled")
        self.progress_var.set(0)
        self.phase_var.set("Starting…")
        self.status_var.set("Generating…")
        threading.Thread(target=self._worker, args=(settings,), daemon=True).start()

    def _worker(self, settings: dict):
        try:
            self._generate(settings)
        except Exception:
            self.log_queue.put("\nERROR:\n" + traceback.format_exc() + "\n")
            self.log_queue.put(("generation_done", False))
        else:
            self.log_queue.put(("generation_done", True))

    def _generate(self, settings: dict):
        input_path = resolve_user_path(settings["input_path"])
        output_dir = resolve_user_path(settings["output_dir"])
        name = settings["name"]
        self._set_phase(0, "Validating input")

        if not input_path.exists():
            raise FileNotFoundError(
                f"File not found: {input_path.resolve()}"
            )

        if not name:
            raise ValueError("Enter a benchmark name.")
        if name in {".", ".."} or any(c in name for c in '/\\:*?"<>|'):
            raise ValueError("Benchmark name must not contain path separators or invalid filename characters.")

        class_count = self._int_value(
            settings["classes"],
            "Number of classes",
        )

        sampling_mode = settings["sampling_mode"]
        class_selection_mode = settings["class_selection_mode"]

        if sampling_mode not in {"percentage", "fixed", "all", "classes_only"}:
            raise ValueError(
                f"Unsupported sampling mode: {sampling_mode}"
            )

        if class_selection_mode not in {"abox_aware", "tbox_oriented"}:
            raise ValueError(
                f"Unsupported class selection mode: {class_selection_mode}"
            )

        if sampling_mode == "percentage":
            try:
                percentage = float(
                    settings["percentage"].replace(",", ".")
                )
            except ValueError as exc:
                raise ValueError(
                    "Percentage must be a number."
                ) from exc

            if percentage <= 0 or percentage > 100:
                raise ValueError(
                    "Percentage must be > 0 and <= 100."
                )

            individual_count = None

        elif sampling_mode == "fixed":
            percentage = None
            individual_count = self._int_value(
                settings["instances"],
                "Number of individuals",
                allow_zero=True,
            )

        elif sampling_mode == "all":
            percentage = 100.0
            individual_count = None

        else:
            # classes_only
            percentage = None
            individual_count = 0

        seed = self._int_value(
            settings["seed"],
            "Seed",
            allow_zero=True,
        )

        options = settings["options"]

        self.log_queue.put(
            "\n=== Benchmark generation ===\n"
        )

        self._set_phase(5, "Loading source ontology")
        source = Graph()
        source.parse(input_path)
        self._set_phase(18, "Source ontology loaded")

        input_profile = ontology_semantic_profile(source)
        self._set_phase(27, "Source statistics computed")

        all_classes = get_classes(source)
        all_object_properties = get_object_properties(
            source
        )

        if class_count > len(all_classes):
            raise ValueError(
                f"{class_count} classes were requested, "
                f"but the FULL dataset contains only {len(all_classes)}."
            )

        dependencies = build_class_dependencies(
            source,
            all_classes,
            options["include_subclass"],
            options["include_metamodeling"],
        )

        # ----------------------------------------------------
        # Class selection
        # ----------------------------------------------------
        if class_selection_mode == "tbox_oriented":
            selected_classes = select_classes_tbox_oriented(
                source,
                all_classes,
                dependencies,
                class_count,
                seed,
            )
        else:
            # Fixed-total sampling benefits from ABox-aware class selection.
            # Percentage/all/classes-only modes use dependency-safe selection.
            if sampling_mode == "fixed":
                selected_classes = select_classes_abox_aware(
                    source,
                    all_classes,
                    dependencies,
                    class_count,
                    individual_count,
                    seed,
                )
            else:
                class_order = dependency_safe_order(
                    all_classes,
                    dependencies,
                    seed,
                )
                selected_classes = set(
                    class_order[:class_count]
                )

        self._set_phase(43, "Classes selected")

        # ----------------------------------------------------
        # Individual sampling
        # ----------------------------------------------------
        if sampling_mode in {"percentage", "all"}:
            (
                selected_individuals,
                eligible_types,
                strata,
                primary_stratum,
            ) = select_individuals_by_percentage(
                source,
                all_classes,
                selected_classes,
                percentage,
                seed,
            )

        elif sampling_mode == "fixed":
            selected_individuals, eligible_types, strata = (
                select_individuals(
                    source,
                    all_classes,
                    selected_classes,
                    individual_count,
                    seed,
                )
            )
            primary_stratum = {}

        else:
            # Classes-only benchmark:
            # no ordinary individuals are retained.
            # Metamodeling assertions are preserved by filter_graph()
            # because class subjects are handled independently.
            selected_individuals = set()

            all_types = get_ordinary_individual_types(
                source,
                all_classes,
            )

            eligible_types = {
                individual: (types & selected_classes)
                for individual, types in all_types.items()
                if types & selected_classes
            }

            strata = Counter()
            primary_stratum = {}

        self._set_phase(57, "Individuals selected")

        self.log_queue.put(
            f"Class selection: {class_selection_mode}\n"
            f"Individual sampling: {sampling_mode}\n"
            + (
                f"Sampling percentage: {percentage:g}%\n"
                if percentage is not None
                else ""
            )
            + f"FULL classes: {len(all_classes)}\n"
            f"Selected classes: {len(selected_classes)}\n"
            f"Eligible individuals: {len(eligible_types)}\n"
            f"Selected individuals: {len(selected_individuals)}\n"
            f"Primary strata: {len(strata)}\n"
        )

        self._set_phase(60, "Filtering RDF graph")
        result = filter_graph(
            source,
            selected_classes,
            selected_individuals,
            all_classes,
            all_object_properties,
            options,
        )
        self._set_phase(74, "Output graph filtered")

        output_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        owl_path = output_dir / f"{name}.owl"
        config_path = output_dir / f"{name}_config.json"
        stats_path = output_dir / f"{name}_stats.tsv"
        semantic_json_path = output_dir / f"{name}_semantic_report.json"
        semantic_txt_path = output_dir / f"{name}_semantic_report.txt"
        output_files = (owl_path, config_path, stats_path,
                        semantic_json_path, semantic_txt_path)
        if not settings["overwrite"]:
            existing = [str(p) for p in output_files if p.exists()]
            if existing:
                raise FileExistsError(
                    "Output file(s) already exist. Enable overwrite or change the "
                    "benchmark name:\n" + "\n".join(existing)
                )

        self._set_phase(78, "Computing semantic profile")
        output_profile = ontology_semantic_profile(result)
        self._set_phase(83, "Serializing OWL")
        result.serialize(destination=str(owl_path), format="xml")
        self._set_phase(90, "OWL saved")

        stats = benchmark_stats(
            result,
            selected_classes,
            selected_individuals,
        )

        stats["eligible_ordinary_individuals"] = len(
            eligible_types
        )
        stats["represented_primary_strata"] = len(
            strata
        )
        stats["sampling_percentage"] = (
            percentage
            if percentage is not None
            else ""
        )

        config = {
            "input_owl": portable_config_path(input_path),
            "output_owl": portable_config_path(owl_path),
            "input_owl_external": is_external_path(input_path),
            "output_owl_external": is_external_path(owl_path),
            "seed": seed,
            "requested_classes": class_count,
            "class_selection_mode": class_selection_mode,
            "individual_sampling_mode": sampling_mode,
            "requested_percentage_per_primary_stratum": percentage,
            "requested_fixed_individuals": individual_count,
            "selected_ordinary_individuals": len(selected_individuals),
            "represented_primary_strata": len(strata),
            "ordinary_individuals_removed": (
                sampling_mode == "classes_only"
            ),
            "metamodeling_preserved": (
                options["include_metamodeling"]
            ),
            "features": options,
            "statistics": stats,
        }

        self._set_phase(92, "Writing configuration and statistics")
        config_path.write_text(
            json.dumps(
                config,
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        with stats_path.open(
            "w",
            encoding="utf-8",
            newline="",
        ) as handle:
            writer = csv.writer(
                handle,
                delimiter="\t",
            )
            writer.writerow(["metric", "value"])

            for key, value in stats.items():
                writer.writerow([key, value])

        semantic_json = {
            "benchmark_name": name,
            "source_owl": portable_config_path(input_path),
            "output_owl": portable_config_path(owl_path),
            "source_owl_external": is_external_path(input_path),
            "output_owl_external": is_external_path(owl_path),
            "configuration": {
                "seed": seed,
                "class_selection_mode": class_selection_mode,
                "individual_sampling_mode": sampling_mode,
                "requested_classes": class_count,
                "requested_percentage": percentage,
                "requested_fixed_individuals": individual_count,
                "enabled_features": options,
            },
            "source_ontology": input_profile,
            "generated_benchmark": output_profile,
        }
        semantic_json_path.write_text(
            json.dumps(semantic_json, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        semantic_txt_path.write_text(
            make_semantic_report(
                name=name, input_path=input_path, owl_path=owl_path,
                config=config, input_profile=input_profile,
                output_profile=output_profile,
            ),
            encoding="utf-8",
        )
        self._set_phase(100, "Generated OWL, stats, config and semantic reports")

        self.log_queue.put(
            "\nBenchmark created:\n"
            f"{owl_path}\n\n"
            "Statistics:\n"
        )

        for key, value in stats.items():
            self.log_queue.put(
                f"  {key}: {value}\n"
            )

        self.log_queue.put(
            f"\nConfiguration: {config_path}\n"
            f"Statistics TSV: {stats_path}\n"
            f"Semantic TXT: {semantic_txt_path}\n"
            f"Semantic JSON: {semantic_json_path}\n"
        )

    # --------------------------------------------------------
    # Log / status
    # --------------------------------------------------------

    def _drain_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                if isinstance(message, tuple):
                    event = message[0]
                    if event == "progress":
                        _, pct, label = message
                        self.progress_var.set(pct)
                        self.phase_var.set(f"{int(pct)}% of phases completed — {label}")
                    elif event == "analysis_ready":
                        _, path, signature, profile = message
                        self._analysis_running = False
                        self.analyze_button.configure(state="normal")
                        if not self._generation_running:
                            self.generate_button.configure(state="normal")
                        try:
                            current_input_path = resolve_user_path(self.input_var.get())
                            if (self._file_signature(current_input_path) == signature
                                    and current_input_path == path.resolve()):
                                self._accept_ontology_profile(path, profile, signature)
                        except OSError:
                            pass
                    elif event == "analysis_error":
                        self._analysis_running = False
                        self.analyze_button.configure(state="normal")
                        if not self._generation_running:
                            self.generate_button.configure(state="normal")
                        self.dataset_info_var.set("Analysis failed")
                        messagebox.showerror(APP_TITLE, f"Unable to analyze ontology:\n{message[1]}")
                    elif event == "generation_done":
                        self._finished(message[1])
                    continue

                self.log.configure(state="normal")
                self.log.insert("end", message)
                self.log.see("end")
                self.log.configure(state="disabled")

        except queue.Empty:
            pass

        self.after(100, self._drain_log_queue)

    def _finished(self, success: bool):
        self._generation_running = False
        self.generate_button.configure(state="normal")
        if not self._analysis_running:
            self.analyze_button.configure(state="normal")

        if success:
            self.status_var.set("Completed")
            messagebox.showinfo(APP_TITLE, "Benchmark and semantic reports generated successfully.")
        else:
            self.status_var.set("Error")
            self.phase_var.set("Generation failed — see log for details")
            messagebox.showerror(
                APP_TITLE,
                "An error occurred during generation. Check the log for details.",
            )


def main():
    app = BenchmarkGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
