def plan(columns, indexes):
    statements = []
    if "deleted_at" not in columns:
        statements.append("ALTER TABLE items ADD COLUMN deleted_at TEXT NULL;")
    if "items_deleted_at_idx" not in indexes:
        statements.append("CREATE INDEX items_deleted_at_idx ON items(deleted_at);")
    return statements
