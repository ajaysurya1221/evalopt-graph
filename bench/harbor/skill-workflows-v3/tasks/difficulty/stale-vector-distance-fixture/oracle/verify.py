from service import solve

assert solve(
    {
        "query": [0, 0],
        "weights": [1, 1],
        "records": [{"id": "a", "vector": [3, 0], "tags": []}, {"id": "b", "vector": [2, 2], "tags": []}],
        "required": [],
        "limit": 3,
    }
) == [{"id": "b", "distance": 8}, {"id": "a", "distance": 9}]
