"""Importable DOCX paper-generation core."""

from . import equations, paper_format, paper_workflow, rendering
from .result_contract import write_run_manifest, load_spss_outputs

__all__ = [
    "equations",
    "paper_format",
    "paper_workflow",
    "rendering",
    "write_run_manifest",
    "load_spss_outputs",
]
