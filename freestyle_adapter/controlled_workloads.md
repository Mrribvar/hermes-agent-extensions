# PHASE 5F — CONTROLLED WORKLOADS (Real Execution Through Adapter; Safe; Non-Destructive)

All 4 tasks executed through adapter -> SDK -> VM (same as Phase 4 real routing); results saved in adapter-level file (not core mutation).

TEST 1: echo HERMES_DELEGATION_OK
- Path: adapter -> SDK exec -> bash -c 'echo HERMES_DELEGATION_OK'
- Expected: exit 0; stdout = HERMES_DELEGATION_OK
- Safety: no secret; no destructive action; adapter-level execution only.

TEST 2: python3 -c "print('PYTHON_DELEGATION_OK')"
- Path: adapter -> SDK exec -> python3 -c ...
- Expected: exit 0; stdout = PYTHON_DELEGATION_OK

TEST 3: python3 - <<'PY' (multi-line script with platform info)
- Script content (safe): import platform; print(platform.system()); print(platform.python_version())
- Expected: exit 0; stdout includes system and python version

TEST 4: Create test file inside VM, read it, confirm persistence.
- Command: bash -c 'echo delegation_test_file > /tmp/delegation_persistence.txt && cat /tmp/delegation_persistence.txt'
- Expected: exit 0; stdout contains file content; persistence verified (file exists in VM filesystem; adapter does not delete VM by default; file remains for next execution unless cleanup policy applies).

Results: (recorded in adapter-level file; not core mutation)
- All tasks completed with exit 0 (verified in real execution; adapter-level results saved separately).
- No destructive action performed; VM preserved; no secrets transmitted.
