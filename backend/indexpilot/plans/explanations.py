from indexpilot.plans.models import PlanDocument, PlanObservation
from indexpilot.plans.parser import walk_plan
from indexpilot.schema.models import TableInfo


def explain_plan(document: PlanDocument, tables: list[TableInfo]) -> PlanDocument:
    by_identity = {(table.schema_name, table.name): table for table in tables}
    observations = []
    messages = {
        "Index Scan": "An index narrows row locations, with heap visits for values/visibility.",
        "Index Only Scan": (
            "Requested values can come from the index; visibility checks may require heap visits."
        ),
        "Bitmap Heap Scan": (
            "A bitmap groups heap-page visits; child index scans identify matching row locations."
        ),
        "Bitmap Index Scan": "This index contributes matching row locations to a bitmap.",
        "Nested Loop": (
            "Each outer row uses an inner access path; usefulness depends on outer rows "
            "and inner lookup cost."
        ),
        "Hash Join": "A hash table on one input supports matching join keys from the other input.",
        "Merge Join": "The join processes ordered inputs, using indexes or explicit sorts.",
        "Sort": (
            "An explicit ordering remains; an index removes it only when its order fits the plan."
        ),
        "Incremental Sort": "Partial ordering is supplied; remaining keys sort within groups.",
    }
    for path, node in walk_plan(document.root):
        fraction = None
        if node.node_type in ("Seq Scan", "Parallel Seq Scan"):
            table = by_identity.get((node.schema_name, node.relation_name))
            message = "A sequential scan is not automatically a problem."
            if table:
                if table.estimated_pages <= 8:
                    message += " The table has few pages, so scanning can avoid index overhead."
                if (
                    table.estimated_rows
                    and node.estimated_rows is not None
                    and not node.parallel_aware
                ):
                    fraction = node.estimated_rows / table.estimated_rows
                    if fraction >= 0.2:
                        message += (
                            " The scan is estimated to return a substantial fraction of the table."
                        )
                if not any(index.valid and index.ready and index.live for index in table.indexes):
                    message += " No usable existing index was observed."
            message += " These are possible factors, not proof of the optimizer's internal reason."
        else:
            message = messages.get(node.node_type)
        if message:
            observations.append(
                PlanObservation(
                    node_path=path,
                    node_type=node.node_type,
                    message=message,
                    estimated_output_fraction=fraction,
                )
            )
    return document.model_copy(update={"observations": observations})
