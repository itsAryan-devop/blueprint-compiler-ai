"""The compiler passes.

An English request flows through four stages, each its own module:

    intent  ->  design  ->  schema generation  ->  refinement

A single big LLM call is forbidden; staging is what makes the system reliable.
"""

from pipeline.compiler import CompileResult, compile_app
from pipeline.design import design_system
from pipeline.fast_compile import compile_fast
from pipeline.input_analysis import InputDiagnosis, Severity, analyze_request
from pipeline.intent import extract_intent
from pipeline.refine import refine
from pipeline.schema_gen import (
    generate_api,
    generate_auth,
    generate_business_logic,
    generate_database,
    generate_ui,
)

__all__ = [
    "compile_app", "compile_fast", "CompileResult",
    "analyze_request", "InputDiagnosis", "Severity",
    "extract_intent",
    "design_system",
    "generate_database",
    "generate_auth",
    "generate_api",
    "generate_ui",
    "generate_business_logic",
    "refine",
]
