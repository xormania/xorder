"""Keep CI builders capable of sharing local parents and exporting caches."""
import ast
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def evaluate(expression, line):
    """Evaluate only the startsWith/boolean subset used by builder selection."""
    expression = expression.removeprefix("${{ ").removesuffix(" }}")
    expression = re.sub(r"startsWith\(matrix.line, '([^']+)'\)",
                        lambda match: str(line.startswith(match[1])), expression)
    if re.sub(r"True|False|'docker-container'|'docker'|[()&|\s]", "", expression):
        raise ValueError("Unsupported builder selection expression")
    tree = ast.parse(expression.replace("||", " or ").replace("&&", " and "), mode="eval")

    def value(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.BoolOp):
            result = value(node.values[0])
            for operand in node.values[1:]:
                if isinstance(node.op, ast.And):
                    result = value(operand) if result else result
                elif isinstance(node.op, ast.Or):
                    result = result if result else value(operand)
                else:
                    raise ValueError("Unsupported boolean operator")
            return result
        raise ValueError("Unsupported expression node")

    return value(tree.body)


class ImageBuilderWorkflowTests(unittest.TestCase):
    def test_every_parent_tree_can_share_images_and_export_cache(self):
        source = (ROOT / ".github/workflows/validate.yml").read_text()
        images = source.split("\n  images:\n", 1)[1].split("\n  checks:\n", 1)[0]
        docker = re.search(r"^      - name: [^\n]+\n"
                           r"(?:(?!^      - ).)*docker/setup-docker-action@"
                           r"(?:(?!^      - ).)*", images, re.M | re.S)[0]
        condition = re.search(r"^        if: (.+)$", docker, re.M)[1]
        config = re.search(r"daemon-config: '(.+)'", docker)[1]
        self.assertTrue(json.loads(config)["features"]["containerd-snapshotter"])
        driver = re.search(r"^          driver: (.+)$", images, re.M)[1]
        self.assertLess(images.index(docker), images.index("docker/setup-buildx-action@"))
        definitions = {}
        for path in (ROOT / "images").glob("*/definition.json"):
            definition = json.loads(path.read_text())
            for line, entry in definition["lines"].items():
                definitions[definition["family"] + "/" + line] = entry
        roots = {line for line, entry in definitions.items() if not entry["base"].get("parent")}
        parents = {entry["base"]["parent"] for entry in definitions.values() if entry["base"].get("parent")}
        self.assertTrue(roots & parents)
        for line in sorted(roots):
            with self.subTest(line=line):
                selected = evaluate(condition, line)
                builder = evaluate(driver, line)
                if line in parents:
                    self.assertTrue(selected, f"{line} has children needing a local parent")
                    self.assertEqual(builder, "docker")
                else:
                    self.assertFalse(selected)
                    self.assertEqual(builder, "docker-container")


if __name__ == "__main__":
    unittest.main()
