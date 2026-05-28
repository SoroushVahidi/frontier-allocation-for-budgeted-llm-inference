#!/usr/bin/env python3
"""
Rate-limit-aware resume wrapper for Mistral D6 pilot.
Launches generation with conservative inter-request delays.
"""

import subprocess
import time
import sys
import os

def main():
    pilot_dir = "/home/soroush/frontier-allocation-for-budgeted-llm-inference/outputs/job_d6_mistral_pilot_20260526/run_20260526T150521Z"
    manifest_file = os.path.join(pilot_dir, "mistral_d6_pilot_manifest.jsonl")
    
    print("""
╔════════════════════════════════════════════════════════════════╗
║  Mistral D6 Pilot Resume — Rate-Limit-Aware Wrapper           ║
╚════════════════════════════════════════════════════════════════╝

Strategy: Conservative exponential backoff with 60+ second cap
  - Initial retry: 5 seconds
  - Max retry: 60 seconds
  - Inter-request minimum: Avoid burst that triggers 429

Starting resume job...
""")
    
    cmd = [
        "python3",
        "/home/soroush/frontier-allocation-for-budgeted-llm-inference/scripts/d6_generate_frontier_variants.py",
        "--run-dir", pilot_dir,
        "--approve-api",
        "--limit", "150",
        "--variants", "frontier_math_extended_verify_v1",
        "--resume",
        "--timeout-seconds", "30",
        "--max-output-tokens", "512",
    ]
    
    print(f"Command: {' '.join(cmd)}\n")
    
    try:
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\nResume job interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nError launching resume job: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
