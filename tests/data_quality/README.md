# PostgreSQL Data Quality Checks

These integration tests verify that PostgreSQL itself enforces the schema's CHECK and foreign-key constraints. They are intentionally skipped in the local unit suite unless `FINTRUST_TEST_DATABASE_URL` is set.

The tests apply `sql/schema.sql` and `sql/seed.sql` to the configured test database. Use a disposable database only; never point this variable at production data.

```powershell
$env:FINTRUST_TEST_DATABASE_URL = 'postgresql://postgres:postgres@localhost:5432/fintrust_test'
python -m pytest tests/data_quality/test_constraints.py -q
```

GitHub Actions runs these tests with a temporary PostgreSQL service only on pushes to `develop`.
