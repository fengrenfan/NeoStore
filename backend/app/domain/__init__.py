"""Domain layer: pure business logic.

Modules under ``app.domain`` must never import FastAPI/Starlette and must never
hold a database ``Session`` directly — persistence goes through repositories.
"""

from importlib import import_module

# Importing every model module guarantees they are registered on ``Base.metadata``
# before Alembic autogenerate or ``create_all`` runs.
_MODEL_MODULES = (
    "app.domain.admin.models",
    "app.domain.i18n.models",
    "app.domain.currency.models",
    "app.domain.region.models",
    "app.domain.catalog.models",
    "app.domain.inventory.models",
    "app.domain.cart.models",
    "app.domain.order.models",
)


def load_models() -> None:
    for module in _MODEL_MODULES:
        try:
            import_module(module)
        except ModuleNotFoundError:
            # A module that has not been implemented yet is fine during
            # incremental delivery; swallow only that exact case.
            continue
