from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import socket

import pytest

from app import project_contract as pc

STUDIO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = STUDIO_ROOT / "examples" / "fabric-project"


@pytest.fixture
def project():
    return pc.load_manifest(EXAMPLES / "foil.project.json")


def test_foil_json_and_yaml_are_equal_design_only_projects(project):
    yaml_project = pc.load_manifest(EXAMPLES / "fabric-project.yaml")
    assert yaml_project == project
    result = pc.validate_project(project)
    assert result.valid
    assert result.deployable is False


def test_unknown_field_and_runtime_ids_are_rejected(project):
    project["approveAll"] = True
    assert any(f.code == "schema.unknown_field" for f in pc.validate_project(project).findings)
    project = pc.load_manifest(EXAMPLES / "foil.project.json")
    project["resources"][0]["nativeItemId"] = "remote-id"
    assert any(f.code == "schema.unknown_field" for f in pc.validate_project(project).findings)


def test_duplicate_key_path_dependency_and_cycle_checks(project):
    duplicate = deepcopy(project)
    duplicate["resources"][1]["key"] = duplicate["resources"][0]["key"]
    assert any(f.code == "resource.duplicate_key" for f in pc.validate_project(duplicate).findings)

    duplicate_path = deepcopy(project)
    duplicate_path["resources"][1]["definitionPath"] = duplicate_path["resources"][0]["definitionPath"].upper()
    assert any(f.code == "path.duplicate" for f in pc.validate_project(duplicate_path).findings)

    missing = deepcopy(project)
    missing["resources"][0]["dependsOn"] = ["missing"]
    assert any(f.code == "dependency.missing" for f in pc.validate_project(missing).findings)

    cycle = deepcopy(project)
    cycle["resources"][0]["dependsOn"] = ["telemetry_db"]
    assert any(f.code == "dependency.cycle" for f in pc.validate_project(cycle).findings)


@pytest.mark.parametrize("value", [
    "../outside", "/absolute/path", "C:/outside", "C:\\outside", "\\\\server\\share",
    "folder\\escape", "a/../b", "a//b", "./a", ".git/config", "a/NUL.txt", "a/b.", "a/b ", "a/\x00b", "a/x*y",
])
def test_unsafe_lexical_paths_are_rejected(project, value):
    assert not pc.safe_relative_path(value)
    mutated = deepcopy(project)
    mutated["resources"][0]["definitionPath"] = value
    assert any(f.code == "path.unsafe" for f in pc.validate_project(mutated).findings)


def test_unknown_profile_is_rejected(project):
    result = pc.validate_project(project, profile_name="missing")
    assert any(f.code == "profile.unknown" for f in result.findings)
    with pytest.raises(pc.ProjectContractError, match="Unknown profile"):
        pc.resolve_profile(project, "missing")


def test_native_git_is_dev_only(project):
    project["profiles"]["prod"]["deploymentOwner"] = "native-git"
    assert any(f.code == "profile.native_git_scope" for f in pc.validate_project(project).findings)


def test_unknown_flow_and_duplicate_flow_are_rejected(project):
    project["dataFlows"][0]["to"] = "missing"
    assert any(f.code == "flow.unknown_endpoint" for f in pc.validate_project(project).findings)
    project = pc.load_manifest(EXAMPLES / "foil.project.json")
    project["dataFlows"].append(deepcopy(project["dataFlows"][0]))
    assert any(f.code == "flow.duplicate" for f in pc.validate_project(project).findings)


def test_inline_credentials_and_secret_fields_are_rejected(project):
    secret_field = deepcopy(project)
    secret_field["profiles"]["dev"]["clientSecret"] = "fake"
    findings = pc.validate_project(secret_field).findings
    assert any(f.code in {"schema.unknown_field", "security.inline_credential"} for f in findings)

    inline = deepcopy(project)
    inline["displayName"] = "AccountKey=fake-not-a-real-secret"
    assert any(f.code == "security.inline_credential" for f in pc.validate_project(inline).findings)


def test_duplicate_json_and_yaml_mapping_keys_are_rejected(tmp_path):
    json_path = tmp_path / "duplicate.json"
    json_path.write_text('{"projectId":"a","projectId":"b"}', encoding="utf-8")
    with pytest.raises(pc.ProjectContractError) as json_error:
        pc.load_manifest(json_path)
    assert json_error.value.code == "parse.duplicate_key"

    yaml_path = tmp_path / "duplicate.yaml"
    yaml_path.write_text("projectId: a\nprojectId: b\n", encoding="utf-8")
    with pytest.raises(pc.ProjectContractError) as yaml_error:
        pc.load_manifest(yaml_path)
    assert yaml_error.value.code == "parse.duplicate_key"


def test_yaml_aliases_are_rejected(tmp_path):
    path = tmp_path / "alias.yaml"
    path.write_text("a: &x {b: 1}\nc: *x\n", encoding="utf-8")
    with pytest.raises(pc.ProjectContractError) as error:
        pc.load_manifest(path)
    assert error.value.code == "parse.yaml_alias"


def test_size_limit(tmp_path):
    path = tmp_path / "too-large.json"
    path.write_bytes(b" " * (pc.MAX_MANIFEST_BYTES + 1))
    with pytest.raises(pc.ProjectContractError) as error:
        pc.load_manifest(path)
    assert error.value.code == "parse.size"


def test_symlink_escape_is_rejected_before_native_file_access(tmp_path):
    root = tmp_path / "project"
    outside = tmp_path / "outside"
    root.mkdir(); outside.mkdir()
    (outside / "secret.txt").write_text("do not read", encoding="utf-8")
    link = root / "fabric"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks unavailable on this runner")
    with pytest.raises(pc.ProjectContractError) as error:
        pc.resolve_trusted_definition(root, "fabric/secret.txt", must_exist=True)
    assert error.value.code == "path.escape"


def test_manifest_save_never_rewrites_native_definition(tmp_path, project):
    root = tmp_path / "repo"
    native = root / "fabric" / "FoilQuality.Notebook" / "notebook-content.bin"
    native.parent.mkdir(parents=True)
    original = b"opaque-native-content\x00\xff"
    native.write_bytes(original)

    json_target = root / "fabric-project.json"
    yaml_target = root / "fabric-project.yaml"
    pc.save_manifest(json_target, project, project_root=root)
    pc.save_manifest(yaml_target, project, project_root=root)
    assert native.read_bytes() == original
    assert pc.load_manifest(json_target) == project
    assert pc.load_manifest(yaml_target) == project


def test_manifest_target_cannot_escape_project_root(tmp_path, project):
    root = tmp_path / "repo"; root.mkdir()
    with pytest.raises(pc.ProjectContractError) as error:
        pc.save_manifest(tmp_path / "outside.json", project, project_root=root)
    assert error.value.code == "path.escape"


def test_offline_validation_never_opens_network(project, monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("offline project validation attempted network access")
    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    assert pc.validate_project(project, profile_name="dev").valid


def test_generated_frontend_contract_matches_canonical_schema():
    generator_path = STUDIO_ROOT / "scripts" / "generate_project_contract.py"
    spec = importlib.util.spec_from_file_location("project_codegen", generator_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    schema = json.loads((STUDIO_ROOT / "contracts" / "project.schema.json").read_text(encoding="utf-8"))
    expected = module.render(schema)
    actual = (STUDIO_ROOT / "frontend" / "src" / "data" / "project-contract.generated.ts").read_text(encoding="utf-8")
    assert actual == expected


def test_validation_payload_keeps_design_only_boundary(project):
    payload = pc.validation_payload(pc.validate_project(project))
    assert payload["valid"] is True
    assert payload["deployable"] is False
    assert payload["project"]["projectId"] == "foil"
