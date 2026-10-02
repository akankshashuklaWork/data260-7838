# AI Use Disclosure

1. I used an AI assistant to inspect the HW5 instructions and DATA236_Demo5, extend the existing FastAPI/SQLAlchemy rental service, add Redux Toolkit client code, draft the MCP servers and retry harness, and prepare test and evidence scripts. I reviewed the design, selected the rental-domain related entity, ran the checks, and retained responsibility for the final submission and report.

2. One independently verified result was the relationship behavior: deleting an owner with an associated listing must return HTTP 409 rather than silently deleting the owner.

3. I detected this with a fresh SQLite TestClient smoke test that registers and logs in a user, creates an owner, creates a listing, queries the owner relationship endpoint, and attempts the restricted owner deletion.

4. I kept the foreign key `ondelete=RESTRICT`, added an explicit CRUD-level association check, and mapped the failure to a clear 409 response. The same behavior is covered by the HW5 API smoke check and does not depend on MySQL data already being present.

