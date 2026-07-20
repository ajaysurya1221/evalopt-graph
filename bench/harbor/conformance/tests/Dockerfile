FROM python:3.12-slim

COPY test.sh build_observation.py minimal_policy.py ungoverned_policy.py observation.json evalopt_graph-*.whl /tests/
RUN chmod +x /tests/test.sh && pip install --no-cache-dir /tests/evalopt_graph-*.whl
