"""Small executable guardrails for the teaching architecture."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"

def imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module

def test_domains_do_not_import_frameworks_or_outer_layers():
    for directory in ROOT.glob("*/domain"):
        for path in directory.rglob("*.py"):
            for module in imports(path):
                assert module.split(".")[0] not in {"fastapi", "sqlalchemy", "pydantic"}, path
                assert not any(part in module.split(".") for part in ("presentation", "application", "infrastructure", "wiring")), path

def test_application_and_presentation_boundaries():
    for layer in ("application", "presentation"):
        for directory in ROOT.glob(f"*/{layer}"):
            for path in directory.rglob("*.py"):
                for module in imports(path):
                    assert "infrastructure" not in module.split("."), path
                    assert "wiring" not in module.split("."), path
                    assert module.split(".")[0] != "sqlalchemy", path
                    if layer == "application":
                        assert module.split(".")[0] != "fastapi", path
                        assert "presentation" not in module.split("."), path


def test_standard_assignment_layout_and_one_entrypoint():
    assert (ROOT / 'main.py').is_file()
    assert (ROOT / 'database.py').is_file()
    assert (ROOT / 'templates' / 'catalog.html').is_file()
    assert (ROOT / 'static' / 'styles.css').is_file()
    assert not (ROOT / 'premium_food_api').exists()
    assert not (ROOT.parent / 'main.py').exists()
    for feature in ('auth', 'user', 'products', 'orders', 'board'):
        assert (ROOT / feature / '__init__.py').is_file()
        for layer in ('presentation', 'application', 'domain', 'infrastructure'):
            assert (ROOT / feature / layer / '__init__.py').is_file()
        assert (ROOT / feature / 'presentation' / 'router.py').is_file()
        assert (ROOT / feature / 'presentation' / 'schemas.py').is_file()
        assert (ROOT / feature / 'application' / 'service.py').is_file()
        assert (ROOT / feature / 'infrastructure' / 'models.py').is_file()
        assert (ROOT / feature / 'infrastructure' / 'repositories.py').is_file()


def test_old_package_imports_are_absent():
    for path in ROOT.rglob('*.py'):
        assert 'premium_food_api' not in path.read_text(encoding='utf-8'), path
