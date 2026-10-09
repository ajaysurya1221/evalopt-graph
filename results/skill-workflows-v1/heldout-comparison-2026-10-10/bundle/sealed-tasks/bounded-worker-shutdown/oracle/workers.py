from queue import Queue
from threading import Thread

def run_jobs(values, workers):
    if not 1 <= workers <= 8:
        raise ValueError("worker count")
    queue = Queue()
    result = [None] * len(values)
    def work():
        while True:
            job = queue.get()
            try:
                if job is None:
                    return
                index, value = job
                result[index] = value * value
            finally:
                queue.task_done()
    threads = [Thread(target=work) for _ in range(workers)]
    for thread in threads:
        thread.start()
    for job in enumerate(values):
        queue.put(job)
    for _ in threads:
        queue.put(None)
    queue.join()
    for thread in threads:
        thread.join()
    return result
