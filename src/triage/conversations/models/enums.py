"""Controlled vocabularies the system reasons over.

The LLM may only classify *into* these values; it can never invent new ones.
This is the backbone of deterministic, auditable behavior.

`Urgency` and `BusinessImpact` are *ordered* — their members carry a rank from
declaration order so severity can be compared and maxed across multiple issues,
while still serializing as their plain string value.
"""

from enum import StrEnum


class OrderedStrEnum(StrEnum):
    """A string enum whose members are ranked by declaration order.

    Enables ``a < b`` / ``max(...)`` severity comparisons within a single enum
    type, while JSON-serializing as the underlying string value.
    """

    @property
    def rank(self) -> int:
        return list(type(self)).index(self)

    def __lt__(self, other: object) -> bool:
        if isinstance(other, type(self)):
            return self.rank < other.rank
        return NotImplemented

    def __le__(self, other: object) -> bool:
        if isinstance(other, type(self)):
            return self.rank <= other.rank
        return NotImplemented

    def __gt__(self, other: object) -> bool:
        if isinstance(other, type(self)):
            return self.rank > other.rank
        return NotImplemented

    def __ge__(self, other: object) -> bool:
        if isinstance(other, type(self)):
            return self.rank >= other.rank
        return NotImplemented


class IssueCategory(StrEnum):
    authentication = "authentication"
    mobile_app = "mobile_app"
    billing_payments = "billing_payments"
    reporting_analytics = "reporting_analytics"
    platform_outage = "platform_outage"
    api_integrations = "api_integrations"
    account_provisioning = "account_provisioning"
    data_export_privacy = "data_export_privacy"
    how_to_guidance = "how_to_guidance"
    feature_request = "feature_request"
    other = "other"


class CustomerTier(StrEnum):
    trial = "trial"
    free = "free"
    pro = "pro"
    business = "business"
    enterprise = "enterprise"


class Urgency(OrderedStrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    critical = "critical"


class Sentiment(StrEnum):
    positive = "positive"
    neutral = "neutral"
    frustrated = "frustrated"
    angry = "angry"


class BusinessImpact(OrderedStrEnum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    severe = "severe"


class Team(StrEnum):
    tier1_support = "tier1_support"
    billing_ops = "billing_ops"
    mobile_engineering = "mobile_engineering"
    platform_sre = "platform_sre"
    data_reporting = "data_reporting"
    identity_access = "identity_access"
    api_integrations_team = "api_integrations_team"
    account_management = "account_management"
    trust_privacy = "trust_privacy"


class AffectedComponent(StrEnum):
    web_app = "web-app"
    mobile_app_ios = "mobile-app-ios"
    mobile_app_android = "mobile-app-android"
    auth_service = "auth-service"
    billing_service = "billing-service"
    reporting_service = "reporting-service"
    api_gateway = "api-gateway"
    data_warehouse = "data-warehouse"


class EscalationLevel(StrEnum):
    none = "none"
    tier2 = "tier2"
    on_call_engineering = "on_call_engineering"
    account_manager = "account_manager"
    incident = "incident"


class NextAction(StrEnum):
    auto_resolve_with_kb = "auto_resolve_with_kb"
    route_to_queue = "route_to_queue"
    request_more_info = "request_more_info"
    escalate_to_oncall = "escalate_to_oncall"
    create_incident = "create_incident"
    notify_account_manager = "notify_account_manager"
    offer_workaround = "offer_workaround"
    schedule_callback = "schedule_callback"


class ConversationStatus(StrEnum):
    active = "active"
    awaiting_customer = "awaiting_customer"
    resolved = "resolved"
    reopened = "reopened"
    closed = "closed"


# Category -> default owning team (the deterministic routing baseline).
DEFAULT_TEAM_BY_CATEGORY: dict[IssueCategory, Team] = {
    IssueCategory.authentication: Team.identity_access,
    IssueCategory.mobile_app: Team.mobile_engineering,
    IssueCategory.billing_payments: Team.billing_ops,
    IssueCategory.reporting_analytics: Team.data_reporting,
    IssueCategory.platform_outage: Team.platform_sre,
    IssueCategory.api_integrations: Team.api_integrations_team,
    IssueCategory.account_provisioning: Team.account_management,
    IssueCategory.data_export_privacy: Team.trust_privacy,
    IssueCategory.how_to_guidance: Team.tier1_support,
    IssueCategory.feature_request: Team.tier1_support,
    IssueCategory.other: Team.tier1_support,
}
