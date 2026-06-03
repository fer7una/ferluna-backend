class DatabaseDisabledError(RuntimeError):
    pass


class DatabaseDependencyError(RuntimeError):
    pass


class RevisionConflictError(RuntimeError):
    pass
