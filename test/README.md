# Tests

Test suite for AirAlarmUA (`pytest` + `pytest-asyncio`).

## Layout

```text
test/
├── conftest.py      # shared fixtures (mock env)
├── test_app.py      # app factory, endpoints, OpenAPI
└── test_services.py # services, wiring, domain models
```

## Run

```bash
pip install -r requirements.txt
pip install -r test/requirements.txt

pytest -v
pytest test/test_app.py -v
pytest test/test_services.py -v
```

With coverage:

```bash
pip install pytest-cov
pytest --cov=. --cov-report=term-missing
```
