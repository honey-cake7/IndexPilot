from indexpilot.errors import DomainError


class RunCache:
    """Only valid for one held session's fixed workload/settings; never shared globally."""

    def __init__(self, max_sets=65):
        self.max_sets = max_sets
        self.values = {}

    def get(self, key):
        value = self.values.get(frozenset(key))
        return value.model_copy(deep=True) if value is not None else None

    def put(self, key, value):
        key = frozenset(key)
        self.require_room(key)
        self.values[key] = value.model_copy(deep=True)

    def require_room(self, key):
        if frozenset(key) not in self.values and len(self.values) >= self.max_sets:
            raise DomainError(
                "evaluation_limit", "The bounded number of index-set evaluations was exceeded."
            )
