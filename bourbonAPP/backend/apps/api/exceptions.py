"""Normalização de erros da API: todo erro vira {"detail", "code"} (+ "fields").

Mapa de códigos:
    throttle       -> 429 throttled
    sem auth       -> 401 not_authenticated
    token inválido -> 401 invalid_token
    sem permissão  -> 403 permission_denied
    body/estado    -> 400 invalid_request (+ "fields" para ValidationError)
"""

from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    ErrorDetail,
    NotAuthenticated,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.views import exception_handler


class ApiError(APIException):
    """Erro de API com (status_code, code, detail) explícitos."""

    def __init__(self, status_code, code, detail):
        self.status_code = status_code
        self.default_code = code
        super().__init__(detail)


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return response

    detail = None
    fields = {}
    if isinstance(response.data, dict):
        detail = response.data.get("detail")
        fields = {key: value for key, value in response.data.items() if key != "detail"}
    elif response.data is not None:
        detail = response.data

    code = getattr(exc, "default_code", None) or "invalid_request"
    if isinstance(detail, ErrorDetail) and detail.code:
        code = detail.code
    text = str(detail) if detail is not None else ""

    if isinstance(exc, Throttled):
        code = "throttled"
        text = "Limite de requisições excedido. Tente novamente mais tarde."
    elif isinstance(exc, NotAuthenticated):
        code = "not_authenticated"
        text = "Autenticação necessária."
    elif isinstance(exc, AuthenticationFailed):
        if code == "authentication_failed":
            code = "invalid_token"
        text = text or "Token inválido ou expirado."
    elif isinstance(exc, PermissionDenied):
        code = "permission_denied"
        text = "Permissão negada."
    elif isinstance(exc, ValidationError):
        code = "invalid_request"

    payload = {"detail": text, "code": code}
    if fields:
        payload["fields"] = fields
    response.data = payload
    return response
