"""Erros de domínio com mensagens próprias para o usuário."""
from __future__ import annotations


class SimError(Exception):
    """Erro com mensagem que pode ser exibida ao usuário."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def descricao(self) -> str:
        """Texto completo para mostrar na tela (em ValidationError, inclui o motivo de cada campo)."""
        return self.message


class ValidationError(SimError):
    """Dados inválidos. `errors` mapeia campo -> mensagem."""

    def __init__(self, errors: dict[str, str], message: str = "Corrija os campos indicados."):
        super().__init__(message)
        self.errors = errors

    def descricao(self) -> str:
        detalhes = [m for m in self.errors.values() if m and m != self.message]
        if not detalhes:
            return self.message
        if len(detalhes) == 1:
            return detalhes[0]
        return self.message + "\n\n" + "\n".join(f"- {m}" for m in detalhes)

    def __str__(self) -> str:  # facilita depuração e testes
        detalhes = "; ".join(f"{k}: {v}" for k, v in self.errors.items())
        return f"{self.message} ({detalhes})"


class NotFoundError(SimError):
    """Registro não existe (excluído por outra pessoa, ID inválido etc.)."""


class AuthorizationError(SimError):
    """Usuário autenticado sem permissão para a operação solicitada."""


class PersistenceError(SimError):
    """Falha técnica ao gravar. A causa fica no log; `ref` identifica a ocorrência."""

    def __init__(self, message: str, ref: str):
        super().__init__(message)
        self.ref = ref


class ConflictError(SimError):
    """O registro foi alterado ou excluído por outra pessoa desde que o formulário foi aberto."""
