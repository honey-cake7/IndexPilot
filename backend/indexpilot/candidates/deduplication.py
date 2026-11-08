from indexpilot.candidates.models import CandidateDefinition
from indexpilot.schema.models import IndexInfo


def _key_signature(key):
    return (
        key.attribute_number,
        key.operator_class_oid,
        key.collation_oid,
        key.descending,
        key.nulls_first,
    )


def compare_existing(candidate: CandidateDefinition, indexes: list[IndexInfo]):
    signature = [
        (
            key.attribute_number,
            key.operator_class.oid,
            key.collation_oid,
            key.descending,
            key.nulls_first,
        )
        for key in candidate.keys
    ]
    exact, unique, overlap, warnings = [], [], [], []
    for index in indexes:
        if index.method != "btree" or not (index.valid and index.ready and index.live):
            continue
        if index.predicate is not None or index.expressions is not None:
            continue
        existing = [_key_signature(key) for key in index.keys]
        if existing == signature and not index.included_columns:
            (unique if index.unique else exact).append(index.name)
        elif existing == signature:
            overlap.append(index.name)
            warnings.append(
                "An existing covering index has the same search keys; payload and size differ."
            )
        elif len(existing) > len(signature) and existing[: len(signature)] == signature:
            overlap.append(index.name)
            warnings.append(
                "A longer index shares this prefix; usefulness and storage need evaluation."
            )
        elif len(existing) == len(signature) and all(
            old[:3] == new[:3] and old[3] != new[3] and old[4] != new[4]
            for old, new in zip(existing, signature, strict=True)
        ):
            overlap.append(index.name)
            warnings.append(
                "An existing index can provide the reversed ordering by a backward scan."
            )
    if exact:
        return "exact_duplicate", sorted(exact), warnings
    if unique:
        return "covered_by_unique_index", sorted(unique), warnings
    return None, sorted(overlap), sorted(set(warnings))
