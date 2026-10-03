"""
Module: IPGov_Chatbot/modules/mod06_ast_enforcer
Chức năng: Hàng rào bảo mật và cưỡng chế an toàn tầng AST (Security Guardrails & AST Enforcer).
Căn cứ:
- Blueprint: 04_SECURITY_GUARDRAILS_VA_AST_ENFORCEMENT.md
- Specification: IPGov_Chatbot/docs/MODULE_06_AST_ENFORCER_SPEC.md
"""

from IPGov_Chatbot.modules.mod06_ast_enforcer.ast_enforcer_service import (
    ASTEnforcerService,
    SecurityEnforcementError,
    ALLOWED_SCHEMAS,
    ALLOWED_TABLES,
)
from IPGov_Chatbot.modules.mod06_ast_enforcer.scope_visitor import RecursiveScopeVisitor
from IPGov_Chatbot.schemas.ast_enforcer_dto import (
    ASTViolationType,
    SanitizedSQLDTO,
    SanitizedSubqueryTaskItem,
    SecurityViolationDTO,
)

__all__ = [
    "ASTEnforcerService",
    "SecurityEnforcementError",
    "RecursiveScopeVisitor",
    "SanitizedSQLDTO",
    "SanitizedSubqueryTaskItem",
    "SecurityViolationDTO",
    "ASTViolationType",
    "ALLOWED_TABLES",
    "ALLOWED_SCHEMAS",
]
