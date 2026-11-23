# ES5510 trace divergence report

Classification: **divergence_observed**

Left: `synthetic-ROM01-reference-fixture` (synthetic-reference-fixture)
Right: `synthetic-ROM01-candidate-fixture` (synthetic-candidate-fixture)

## Earliest confirmed divergence

- Frame: 0
- Category: `register_write_ordering`
- Kind: `frame_offset`
- Event: `register_write`
- Reason: same observed event/value appears at a different DSP frame; frame timestamps only

Supporting entries:
```json
{
  "left": {
    "frame": 0,
    "event_order": 1,
    "instruction_index": 0,
    "event_type": "register_write",
    "register": 122,
    "value": 100,
    "source": "synthetic"
  },
  "right": {
    "frame": 1,
    "event_order": 1,
    "instruction_index": 0,
    "event_type": "register_write",
    "register": 122,
    "value": 100,
    "source": "synthetic"
  }
}
```

## Timeline around first mismatch

| Side | Frame | Boundary | Type | Key observation |
|---|---:|---:|---|---|
| left | 0 | 0 | instruction | 0 |
| right | 0 | 0 | instruction | 0 |
| left | 0 | 0 | register_write | 122 |
| right | 1 | 0 | register_write | 122 |

## Findings

| Status | Frame | Category | Finding |
|---|---:|---|---|
| confirmed_mismatch | 0 | `register_write_ordering` | frame_offset |

## Missing observations and limits

- No missing fields were encountered among compared event pairs.
- No DSP arithmetic is inferred from absent fields.
- Frame-level timestamps do not establish instruction-cycle timing.
- No transformation is treated as a correction without independent execution and output validation.
