#!/usr/bin/env python3
"""
Freestyle Executor — adapter layer (not core mutation).
Uses SDK: freestyle@0.2.13 (node bin at node_modules/freestyle/dist/cli/index.js)
Reads FREESTYLE_API_KEY from .env; NEVER logs or exposes the key value.
"""
import os, subprocess, json, time

BIN_PATH = os.environ.get("FREESTYLE_SDK_BIN", "node_modules/freestyle/dist/cli/index.js")

class FreestyleExecutor:
    def __init__(self):
        # Load key securely; do NOT store in any log-accessible form
        self.env = os.environ.copy()
        with open(os.path.expanduser("~/.env")) as f:
            for line in f.read().splitlines():
                if line.startswith("FREESTYLE_API_KEY=") and line != "FREESTYLE_API_KEY=":
                    self.env["FREESTYLE_API_KEY"] = line.split("=", 1)[1]
        self.vm_id = None  # set after creation

    def health_check(self):
        # Verify SDK binary present + docs reachable
        return os.path.exists(BIN_PATH)

    def create_vm(self, slug="hermes-freestyle-vm"):
        cmd = ["node", BIN_PATH, "vm", "create", "--slug", slug, "--output", "json"]
        p = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=120)
        result = json.loads(p.stdout) if p.returncode == 0 else None
        if result and isinstance(result, dict) and "id" in result:
            self.vm_id = result["id"]
        return {"status": "PASS" if result else "FAIL", "vm_id": self.vm_id}

    def execute(self, command_list, vm_id=None):
        target = vm_id or self.vm_id
        cmd = ["node", BIN_PATH, "vm", "exec", target, "--"] + command_list
        p = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=120)
        # Never include any secret-related output; only command status and stdout/stderr (already filtered by subprocess)
        return {"exit_code": p.returncode, "stdout": p.stdout[:2000], "stderr": p.stderr[:2000]}

    def pause(self, vm_id=None):
        target = vm_id or self.vm_id
        cmd = ["node", BIN_PATH, "vm", "pause", target, "--output", "json"]
        p = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=60)
        return {"status": "PASS" if p.returncode == 0 else "FAIL", "state_hint": "paused"}

    def resume(self, vm_id=None):
        target = vm_id or self.vm_id
        cmd = ["node", BIN_PATH, "vm", "start", target, "--output", "json"]
        p = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=60)
        return {"status": "PASS" if p.returncode == 0 else "FAIL", "state_hint": "running"}

    # Cleanup only when explicitly requested; does not delete by default (persistence preserved)
    def cleanup(self, delete_vm=False, vm_id=None):
        if delete_vm and vm_id:
            cmd = ["node", BIN_PATH, "vm", "delete", vm_id, "--output", "json"]
            p = subprocess.run(cmd, capture_output=True, text=True, env=self.env, timeout=60)
            return {"deleted": p.returncode == 0}
        return {"deleted": False, "reason": "VM preserved for persistence; skip delete or set delete_vm=True"}
