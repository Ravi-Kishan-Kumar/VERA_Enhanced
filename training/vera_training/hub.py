"""Upload production artifacts to HuggingFace Hub (PRD §17.3)."""

from __future__ import annotations

from pathlib import Path

from app.ml.models.loader import REQUIRED_ARTIFACTS, missing_artifacts


def upload_artifacts(
    model_dir: str | Path,
    repo_id: str,
    token: str,
    names: list[str] | None = None,
    private: bool = True,
) -> list[str]:
    """Upload the named artifacts (default: all required ones). Returns uploaded names.

    Refuses to upload a partial set when ``names`` is omitted, so the Hub repo
    never holds an inconsistent mix of old and new artifacts.
    """
    from huggingface_hub import HfApi

    model_dir = Path(model_dir)
    selected = names or list(REQUIRED_ARTIFACTS)
    if names is None and (missing := missing_artifacts(model_dir)):
        raise FileNotFoundError(f"Refusing partial upload; missing: {missing}")
    api = HfApi(token=token)
    api.create_repo(repo_id, repo_type="model", private=private, exist_ok=True)
    for name in selected:
        api.upload_file(
            path_or_fileobj=str(model_dir / name),
            path_in_repo=name,
            repo_id=repo_id,
            repo_type="model",
            commit_message=f"Update {name}",
        )
    return selected
