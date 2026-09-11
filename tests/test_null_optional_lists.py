import ast
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def assignment_value(path, variable, inputs, prefix=None):
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == variable for target in node.targets):
            expression = ast.Expression(node.value)
            ast.fix_missing_locations(expression)
            return eval(compile(expression, path, "eval"), {}, {"inputs": inputs, "prefix": prefix})
    raise AssertionError(f"Assignment for {variable} not found in {path}")


def load_functions(path, names):
    tree = ast.parse(path.read_text())
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    namespace = {}
    exec(compile(ast.Module(body=functions, type_ignores=[]), path, "exec"), namespace)
    return namespace


class NullOptionalListTests(unittest.TestCase):
    def test_base_vm_null_lists_become_empty_lists(self):
        path = ROOT / "vm/scripts/prepare_base_vm_config.py"
        inputs = {"primary_port_forwards": None, "vm_add_nics": None}
        self.assertEqual([], assignment_value(path, "primary_port_forwards", inputs))
        self.assertEqual([], assignment_value(path, "vm_add_nics", inputs))

    def test_base_vm_populated_lists_are_preserved(self):
        path = ROOT / "vm/scripts/prepare_base_vm_config.py"
        rules = [{"vm_port": "22"}]
        nics = [{"segment_name": "bridge0"}]
        inputs = {"primary_port_forwards": rules, "vm_add_nics": nics}
        self.assertIs(rules, assignment_value(path, "primary_port_forwards", inputs))
        self.assertIs(nics, assignment_value(path, "vm_add_nics", inputs))

    def test_additional_vm_null_lists_become_empty_lists(self):
        path = ROOT / "multi-node/scripts/prepare_additional_vm.py"
        prefix = "vm_2_"
        variables = {
            "my_add_nics": "vm_add_nics",
            "my_add_disks": "additional_disks",
            "usb": "usb_wrapper",
            "gpu": "gpu_wrapper",
            "pcie": "pcie_wrapper",
            "video": "video",
            "serial_port": "serial_port_wrapper",
        }
        inputs = {f"{prefix}{suffix}": None for suffix in variables.values()}
        for variable in variables:
            with self.subTest(variable=variable):
                self.assertEqual([], assignment_value(path, variable, inputs, prefix))

    def test_additional_vm_populated_lists_are_preserved(self):
        path = ROOT / "multi-node/scripts/prepare_additional_vm.py"
        prefix = "vm_2_"
        nics = [{"segment_name": "bridge0"}]
        disks = [{"name": "data-disk"}]
        inputs = {f"{prefix}vm_add_nics": nics, f"{prefix}additional_disks": disks}
        self.assertIs(nics, assignment_value(path, "my_add_nics", inputs, prefix))
        self.assertIs(disks, assignment_value(path, "my_add_disks", inputs, prefix))

    def test_password_capability_returns_secret_name(self):
        capabilities = yaml.safe_load((ROOT / "vm/outputs.yaml").read_text())["capabilities"]
        password_capability = capabilities["vm_password_secret"]
        self.assertEqual({"get_input": "vm_password"}, password_capability["value"])
        self.assertNotIn("get_secret", password_capability["value"])

    def test_vm_result_name_falls_back_to_vm_config(self):
        path = ROOT / "multi-node/scripts/collect_vm_results.py"
        functions = load_functions(path, {"get_vm_name", "build_vm_entry"})
        capabilities = {
            "vm_name": None,
            "vm_name_id": "edge-vm_generated",
            "vm_config": {"name": "edge-vm"},
            "service_tag": "JH3MV94",
            "vm_hostname": "host3",
            "vm_primary_ip": "172.21.101.3",
            "vm_ssh_private_key": "edge_key_private",
        }
        vm_name = functions["get_vm_name"](capabilities)
        result = functions["build_vm_entry"](capabilities, vm_name)
        self.assertEqual("edge-vm", vm_name)
        self.assertEqual("edge-vm", result["name"])
        self.assertEqual("172.21.101.3", result["primary_ip"])
        self.assertNotIn("ssh_private_key_secret", result)
        self.assertNotIn("password", result)


if __name__ == "__main__":
    unittest.main()
