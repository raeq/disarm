- **Minimum Python is now 3.11** (was 3.10). Python 3.10 reached end of life on
  2026-10-01 (PEP 619), and disarm's floor is the oldest Python upstream still supports.
  The extension now targets the stable-ABI floor `abi3-py311`, so a single `cp311-abi3`
  wheel runs on 3.11 and later; no wheel is built for 3.10. On Python 3.10, pip resolves
  the 0.17 series, the last that supports it.
