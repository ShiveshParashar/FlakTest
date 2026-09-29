from rq import Worker

from .redis_client import redis_conn, task_queue


def main():
    worker = Worker([task_queue], connection=redis_conn)
    worker.work()


if __name__ == "__main__":
    main()
