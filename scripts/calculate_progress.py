import numpy as np
import asyncio

tasks_array = np.zeros(10)

async def calculate_progress(i, n):
    for _ in range(n):
        await asyncio.sleep(np.random.random()*3)
        tasks_array[i] += 1
        print(sum(tasks_array) / (len(tasks_array) * n))

async def main():
    tasks = [asyncio.create_task(calculate_progress(i, 6)) for i in range(10)]
    await asyncio.gather(*tasks)

asyncio.run(main())