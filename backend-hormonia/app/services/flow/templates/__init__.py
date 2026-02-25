"""
TOMBSTONED -- Phase 16 (Dead Code Removal)

This package has been decommissioned. The FlowTemplateManager,
FlowTemplateValidator, and FlowTemplateRepository had zero production callers.

Production template management uses:
  - ``app.services.template_loader_pkg`` for template loading
  - ``app.services.flow_template`` for full lifecycle CRUD

Do not import from this package.
"""

raise ImportError(
    "app.services.flow.templates has been tombstoned in Phase 16 (Dead Code Removal). "
    "This package had zero production callers. "
    "Use app.services.template_loader_pkg for template loading, "
    "or app.services.flow_template for lifecycle management."
)
