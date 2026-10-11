from service import solve

assert isinstance(
    solve(
        {
            "nodes": [
                {"id": "a", "rank": 5, "zone": "z1", "physical": "a", "capacity": 1, "alive": True},
                {"id": "b", "rank": 4, "zone": "z1", "physical": "b", "capacity": 1, "alive": True},
            ],
            "replicas": 2,
            "acks": ["a", "b"],
        }
    ),
    (dict, list, str),
)
