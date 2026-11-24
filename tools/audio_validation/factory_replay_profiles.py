"""Evidence-backed factory effect replay profiles.

The profile describes expected loader observations and clock/routing metadata.
It never contains program or register payloads.
"""

PROFILES = {
    "rom01-hall-v4": {
        "effect_id": "ROM-01", "effect_name": "HALL REVERB",
        "active_words": 89, "end_word": 88,
        "instruction_commits": 89, "unique_instruction_addresses": 89,
        "register_commits": 342, "source_paired_gprs": 86,
        "source_instruction_only": 3, "source_aliases": 0,
        "post_run_gpr_events": 213,
        "dsp_rate_hz": 29761.89453125, "host_rate_hz": 44100,
        "serial_route": "-1,-1,1,-1", "host_serial": 0x48,
        "input_ports": [2], "output_ports": [1],
        "program_sha256": None,
        "instruction_aliases": {},
        "selector_raw_last": 79,
    },
    "rom02-44khz-reverb-v1": {
        "effect_id": "ROM-02", "effect_name": "44KHZ REVERB",
        "active_words": 60, "end_word": 59,
        "instruction_commits": 61, "unique_instruction_addresses": 60,
        "register_commits": 283, "source_paired_gprs": 58,
        "source_instruction_only": 1, "source_aliases": 1,
        "post_run_gpr_events": 202,
        "dsp_rate_hz": 44100.0, "host_rate_hz": 44100,
        "serial_route": "-1,-1,1,-1", "host_serial": 0x48,
        "input_ports": [2], "output_ports": [1],
        # Fingerprint of the active image independently correlated to the private ROM-02 EFE.
        "program_sha256": "12119e86d4d232ab7d7ab4278e9c9dbed9db19a6b6eb352bfb29441181da4486",
        "instruction_aliases": {58: 0},
        "selector_raw_last": 95,
    },
}
