# Gate fixture: clean baseline

A minimal plugin tree that satisfies every delivery rule. The gate must report
zero violations here. Each poisoned variant in `test_gate.py` is this tree plus
exactly one documented mutation.
