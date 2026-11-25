# HALL DECAY Independent QA V1 (Superseded)

This first-pass report is retained for history. Its raw-domain observations and the earlier 102/196 arithmetic finding are superseded by [ASR10_HALL_DECAY_INDEPENDENT_VALIDATION_V2.md](ASR10_HALL_DECAY_INDEPENDENT_VALIDATION_V2.md).

Its runtime harness made 127 API calls per direction, including 28 unchanged endpoint calls per direction, and therefore did not model the 99-step LCD UI traversal. It did use a temporary read accessor; the later canonical V2 test uses exactly 99 LCD steps in each direction and checks 990 applied register writes. See [HALL_DECAY_INDEPENDENT_RUNTIME_QA_V2.json](HALL_DECAY_INDEPENDENT_RUNTIME_QA_V2.json) for the accepted machine-readable result.
