import asyncio, argparse
from orchestrator import main as run_agent


if __name__ == "__main__":
  p = argparse.ArgumentParser()
  p.add_argument('task', type=str, help='Natural language task')
  args = p.parse_args()
  asyncio.run(run_agent(args.task))
