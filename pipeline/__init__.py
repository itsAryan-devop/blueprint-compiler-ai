"""The compiler passes.

An English request flows through four stages, each its own module:

    intent  ->  design  ->  schema generation  ->  refinement

A single big LLM call is forbidden; staging is what makes the system reliable.
"""
