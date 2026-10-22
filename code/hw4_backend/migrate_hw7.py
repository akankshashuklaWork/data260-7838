"""One-time schema migration from the HW4 session user table to HW7 JWT roles.

Back up the local database before running this file against MySQL.  It is not
run by the HW7 verifier, which always uses a disposable SQLite database.
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from .database import Base, engine


def main() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        Base.metadata.create_all(bind=engine)
        print("Created new HW7 schema.")
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    with engine.begin() as connection:
        if "username" not in columns:
            connection.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(64)"))
            connection.execute(
                text("UPDATE users SET username = CONCAT('user_', id) WHERE username IS NULL")
            )
            connection.execute(text("ALTER TABLE users MODIFY username VARCHAR(64) NOT NULL"))
            connection.execute(text("CREATE UNIQUE INDEX ix_users_username ON users (username)"))
        if "role" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN role VARCHAR(16) NOT NULL DEFAULT 'reader'")
            )
    print("HW7 user migration complete. Existing accounts have reader role.")


if __name__ == "__main__":
    main()
