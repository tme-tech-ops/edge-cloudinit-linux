import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "vm/scripts/update_checks.py"


def load(names):
    """The named functions and END_STATES from update_checks.py, without its dell imports."""
    tree = ast.parse(SCRIPT.read_text())
    body = [node for node in tree.body
            if (isinstance(node, ast.FunctionDef) and node.name in names)
            or (isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "END_STATES" for t in node.targets))]
    namespace = {}
    exec(compile(ast.Module(body=body, type_ignores=[]), SCRIPT, "exec"), namespace)
    return namespace


class ChangesSomethingTests(unittest.TestCase):
    changes_something = staticmethod(load(["changes_something"])["changes_something"])

    def record(self, **kwargs):
        record = {"old_inputs": {"vcpus": 3, "memory_size": "4GB", "vm_name": "a"},
                  "new_inputs": {}, "old_blueprint_id": "bp", "new_blueprint_id": "bp",
                  "old_blueprint_version": "1.2.0.0", "new_blueprint_version": "1.2.0.0"}
        record.update(kwargs)
        return record

    def test_no_inputs_sent(self):
        self.assertFalse(self.changes_something(self.record()))

    def test_same_values_sent(self):
        self.assertFalse(self.changes_something(self.record(new_inputs={"vcpus": 3, "memory_size": "4GB"})))

    def test_changed_value(self):
        self.assertTrue(self.changes_something(self.record(new_inputs={"vcpus": 6})))

    def test_inputs_not_sent_are_not_changes(self):
        # new_inputs holds only what the update sent; a missing input is not a change to None
        self.assertFalse(self.changes_something(self.record(new_inputs={"vcpus": 3})))

    def test_new_blueprint_revision(self):
        self.assertTrue(self.changes_something(self.record(new_blueprint_version="1.2.0.1")))


class NeedsRepairTests(unittest.TestCase):
    needs_repair = staticmethod(load(["needs_repair"])["needs_repair"])
    healthy = {"installation_status": "active", "deployment_status": "deployed",
               "latest_execution_status": "completed", "unavailable_instances": 0, "drifted_instances": 0}

    def test_healthy(self):
        self.assertFalse(self.needs_repair(self.healthy))

    def test_failed_last_execution(self):
        self.assertTrue(self.needs_repair({**self.healthy, "latest_execution_status": "failed"}))

    def test_not_in_an_end_state(self):
        self.assertTrue(self.needs_repair({**self.healthy, "deployment_status": "requires_attention"}))

    def test_drifted_or_unavailable_instances(self):
        self.assertTrue(self.needs_repair({**self.healthy, "drifted_instances": 1}))
        self.assertTrue(self.needs_repair({**self.healthy, "unavailable_instances": 1}))

    def test_missing_counts(self):
        self.assertFalse(self.needs_repair({**self.healthy, "drifted_instances": None}))


if __name__ == "__main__":
    unittest.main()
