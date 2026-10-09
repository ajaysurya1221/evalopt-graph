from queue import Queue
from threading import Thread

def run_jobs(values, workers):
    if not 1 <= workers <= 8:
        raise ValueError("worker count")
    if not values:
        return []
    queue = Queue()
    result = [None] * len(values)
    def work():
        while True:
            job = queue.get()
            if job is None:
                return
            index, value = job
            result[index] = value * value
            queue.task_done()
    threads = [Thread(target=work, daemon=True) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for job in enumerate(values):
        queue.put(job)
    for _ in threads:
        queue.put(None)
    queue.join()
    return result
