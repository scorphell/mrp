"""Decorator ``throttle_scope`` compatível com views ``@api_view``.

O DRF >= 3.15 removeu o decorator oficial; ``ScopedRateThrottle`` lê o escopo
de ``view.throttle_scope``. Como ``@api_view`` devolve a view enviesada (que
carrega a classe em ``view.cls``), este decorator define o escopo na classe.

Ordem obrigatória (o decorator fica POR CIMA do @api_view):

    @throttle_scope("verify")
    @api_view(["POST"])
    def view(request): ...
"""

from rest_framework.views import APIView


def throttle_scope(scope: str):
    """Define ``throttle_scope = scope`` na classe da view @api_view."""

    def decorator(view):
        cls = getattr(view, "cls", None)
        if cls is not None and issubclass(cls, APIView):
            cls.throttle_scope = scope
        return view

    return decorator
