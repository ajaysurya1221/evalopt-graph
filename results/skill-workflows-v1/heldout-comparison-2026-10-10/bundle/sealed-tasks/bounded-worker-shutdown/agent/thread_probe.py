from threading import enumerate as list_threads
from workers import run_jobs

def inspect_run(values, workers):
    before = set(list_threads())
    output = run_jobs(values, workers)
    live = [thread for thread in list_threads() if thread not in before and thread.is_alive()]
    return {"result": output, "live_threads": len(live)}
