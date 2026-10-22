import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:password@127.0.0.1:3306/s7838_rel")
engine_options = {"pool_pre_ping": True, "pool_recycle": 1800}
# SQLite is used only by the isolated HW7 verification database.  Allow the
# FastAPI test client to use the same temporary database from its worker thread.
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_options)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "before_cursor_execute")
def count_sql_statements(connection, cursor, statement, parameters, context, executemany):
    connection.info["hw4_sql_count"] = connection.info.get("hw4_sql_count", 0) + 1


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
