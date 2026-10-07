"""Concurrent evidence-number reservations must never collide or 500."""
from concurrent.futures import ThreadPoolExecutor


def test_parallel_reservations_get_disjoint_numbers(client, fresh):
    raj = fresh["raj"]

    def reserve(_):
        return client.post("/api/v1/sync/reserve", json={"count": 3}, headers=raj)

    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = list(pool.map(reserve, range(6)))

    assert [r.status_code for r in responses] == [200] * 6, [r.text for r in responses if r.status_code != 200]
    numbers = [n for r in responses for n in r.json()["numbers"]]
    assert len(numbers) == len(set(numbers)) == 18
    assert sorted(numbers) == list(range(17, 35))
