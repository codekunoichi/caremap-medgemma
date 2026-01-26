from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class PromptRef:
    """Reference to a prompt file stored under the repo's /prompts folder."""
    filename: str  # e.g., "medication_prompt_v1.txt"


def _repo_root() -> Path:
    """
    Resolve repository root based on this file location:
    repo/
      prompts/
      src/
        caremap/
          prompt_loader.py  (this file)
    """
    here = Path(__file__).resolve()
    # .../repo/src/caremap/prompt_loader.py -> parents[2] = .../repo
    return here.parents[2]


def prompts_dir() -> Path:
    return _repo_root() / "prompts"


@lru_cache(maxsize=64)
def load_prompt(prompt: PromptRef | str) -> str:
    """
    Load a prompt template from /prompts and return as a string.

    Example:
        txt = load_prompt("lab_prompt_v1.txt")
    """
    filename = prompt.filename if isinstance(prompt, PromptRef) else str(prompt)
    path = prompts_dir() / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def fill_prompt(template: str, variables: dict[str, str]) -> str:
    """
    Substitute {{VARNAME}} placeholders in the template.

    This intentionally uses simple string replacement (not Jinja) to keep
    behavior deterministic and auditable.
    """
    filled = template
    for key, val in variables.items():
        filled = filled.replace(f"{{{{{key}}}}}", str(val))
    return filled
