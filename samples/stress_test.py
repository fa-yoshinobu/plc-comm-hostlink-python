import sys
import time
import asyncio
from hostlink import HostLinkClient, AsyncHostLinkClient


def run_sync_stress(host, port, transport, count=500):
    print(f"\n--- [1] Synchronous Stress Test: {count} iterations ---")
    latencies = []
    errors = 0

    with HostLinkClient(host, port=port, transport=transport) as plc:
        for i in range(count):
            start = time.perf_counter()
            try:
                # Read DM0
                plc.read("DM0.U")
                end = time.perf_counter()
                latencies.append((end - start) * 1000)
                if i % 100 == 0:
                    print(f"Progress: {i}/{count}...")
            except Exception as e:
                print(f"Error at iteration {i}: {e}")
                errors += 1

    if latencies:
        avg = sum(latencies) / len(latencies)
        print(
            f"Results: Avg={avg:.2f}ms, Min={min(latencies):.2f}ms, Max={max(latencies):.2f}ms, Errors={errors}"
        )


async def run_async_concurrency(host, port, transport, tasks_count=20):
    print(f"\n--- [2] Asynchronous Concurrency Test: {tasks_count} parallel tasks ---")

    async with AsyncHostLinkClient(host, port=port, transport=transport) as plc:

        async def task(tid):
            start = time.perf_counter()
            try:
                await plc.read(f"DM{tid}.U")
                end = time.perf_counter()
                return (end - start) * 1000, None
            except Exception as e:
                return 0, str(e)

        start_all = time.perf_counter()
        results = await asyncio.gather(*(task(i) for i in range(tasks_count)))
        end_all = time.perf_counter()

        success = [r[0] for r in results if r[1] is None]
        fails = [r[1] for r in results if r[1] is not None]

        total_time = (end_all - start_all) * 1000
        print(f"Results: {len(success)} success, {len(fails)} fails")
        print(f"Total time for {tasks_count} tasks: {total_time:.2f}ms")
        if success:
            print(f"Avg latency per task: {sum(success) / len(success):.2f}ms")


def run_bulk_test(host, port, transport, words=1000):
    print(f"\n--- [3] Bulk Data Test: {words} words ---")
    with HostLinkClient(host, port=port, transport=transport) as plc:
        try:
            # Test Bulk Read
            start = time.perf_counter()
            data = plc.read_consecutive("DM1000.U", words)
            end = time.perf_counter()
            print(
                f"Bulk Read {words} words: {(end - start) * 1000:.2f}ms (Size: {len(data)} items)"
            )

            # Test Bulk Write
            write_data = [i % 65535 for i in range(words)]
            start = time.perf_counter()
            plc.write_consecutive("DM1000.U", write_data)
            end = time.perf_counter()
            print(f"Bulk Write {words} words: {(end - start) * 1000:.2f}ms")

            print("--- Bulk Test SUCCESS ---")
        except Exception as e:
            print(f"Bulk Test FAILED: {e}")


async def main():
    if len(sys.argv) < 2:
        print("Usage: python stress_test.py <host> [port] [transport]")
        return

    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8501
    transport = sys.argv[3] if len(sys.argv) > 3 else "tcp"

    print(f"STARTING STRESS TEST ON {host}:{port} ({transport})")

    # 1. Sync Stress (Latency & Stability)
    run_sync_stress(host, port, transport, count=500)

    # 2. Async Concurrency (Locking & Async Performance)
    await run_async_concurrency(host, port, transport, tasks_count=50)

    # 3. Bulk Transfer (Packet size limits)
    run_bulk_test(host, port, transport, words=1000)


if __name__ == "__main__":
    asyncio.run(main())
