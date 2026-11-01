"""Original 160 backlog #121: provider candidate due-diligence comparison.

General capabilities are documented in provider-owned sources, NOT evidence that
a Korean or any other merchant/recipient is eligible. No network, money,
account onboarding, PII collection, or provider selection is performed.
Reviewed 2026-11-01; always recheck live provider documents before decisions.
"""
import re

_CAPABILITIES = frozenset(("hosted_checkout", "marketplace_split", "cross_border_payout"))
_ENTITIES = frozenset(("sole_proprietor", "company", "nonprofit"))
_RECIPIENTS = frozenset(("individual", "business"))
_COUNTRY = re.compile(r"[A-Z]{2}\Z")
_CURRENCY = re.compile(r"[A-Z]{3}\Z")

# General product-family capability, not availability by merchant country,
# business form, settlement currency, recipient country, or account tier.
_CATALOG = (
    {
        "id": "stripe_connect",
        "name": "Stripe Connect",
        "general_capabilities": ("hosted_checkout", "marketplace_split",
                                 "cross_border_payout"),
        "official_docs": ("https://docs.stripe.com/connect",
                          "https://docs.stripe.com/currencies"),
        "review_note": "Connect and currency coverage depend on platform and connected-account country.",
    },
    {
        "id": "adyen_marketplaces",
        "name": "Adyen for Platforms / Marketplaces",
        "general_capabilities": ("hosted_checkout", "marketplace_split",
                                 "cross_border_payout"),
        "official_docs": ("https://docs.adyen.com/marketplaces",
                          "https://docs.adyen.com/marketplaces/custom-payouts"),
        "review_note": "Marketplaces onboarding regions and payout rails are separately restricted.",
    },
    {
        "id": "airwallex_connected",
        "name": "Airwallex Connected Accounts / Payouts",
        "general_capabilities": ("marketplace_split", "cross_border_payout"),
        "official_docs": ("https://www.airwallex.com/docs/connected-accounts/about/account-capabilities",
                          "https://www.airwallex.com/docs/payouts/how-airwallex-payouts-work"),
        "review_note": "Connected-account type, KYB, payments and outbound payouts require separate eligibility.",
    },
)


def _code(value, pattern, label):
    if type(value) is not str or pattern.fullmatch(value) is None:
        raise ValueError("invalid " + label)
    return value


def _choice(value, allowed, label):
    if type(value) is not str or value not in allowed:
        raise ValueError("invalid " + label)
    return value


def compare_provider_candidates(*, merchant_country, merchant_entity,
                                charge_currency, recipient_country,
                                payout_currency, recipient_type,
                                required_capabilities=(
                                    "hosted_checkout", "marketplace_split",
                                    "cross_border_payout")):
    """Compare candidate *research*, never authorize actual money or eligibility.

    Inputs intentionally contain only country/currency codes and entity types;
    no account, tax, identity or bank data can be passed through this API.
    """
    merchant_country = _code(merchant_country, _COUNTRY, "merchant_country")
    recipient_country = _code(recipient_country, _COUNTRY, "recipient_country")
    charge_currency = _code(charge_currency, _CURRENCY, "charge_currency")
    payout_currency = _code(payout_currency, _CURRENCY, "payout_currency")
    merchant_entity = _choice(merchant_entity, _ENTITIES, "merchant_entity")
    recipient_type = _choice(recipient_type, _RECIPIENTS, "recipient_type")
    if type(required_capabilities) not in (tuple, list) or not required_capabilities:
        raise ValueError("required_capabilities must be a nonempty list/tuple")
    if any(type(x) is not str or x not in _CAPABILITIES
           for x in required_capabilities):
        raise ValueError("unknown required capability")
    if len(required_capabilities) != len(set(required_capabilities)):
        raise ValueError("duplicate required capability")
    required = frozenset(required_capabilities)
    cross_border = merchant_country != recipient_country
    fx_needed = charge_currency != payout_currency

    rows = []
    for item in _CATALOG:
        general = frozenset(item["general_capabilities"])
        documented = sorted(required & general)
        unverified = sorted(required - general)
        gates = [
            "VERIFY_MERCHANT_COUNTRY_AND_LEGAL_ENTITY_ONBOARDING",
            "VERIFY_CHARGE_CURRENCY_PAYMENT_METHOD_AND_SETTLEMENT",
            "VERIFY_RECIPIENT_COUNTRY_TYPE_AND_PAYOUT_CURRENCY",
            "VERIFY_RECIPIENT_KYC_KYB_TAX_AND_BANK_OR_WALLET_SCHEMA",
            "VERIFY_PROVIDER_CONTRACT_FEES_REFUNDS_AND_RECONCILIATION",
            "VERIFY_SANDBOX_WEBHOOK_SIGNATURE_AND_SECURITY",
            "VERIFY_LEGAL_TAX_AND_REPRESENTATIVE_APPROVAL",
        ]
        if cross_border:
            gates.append("VERIFY_CROSS_BORDER_RESTRICTIONS")
        if fx_needed:
            gates.append("VERIFY_FX_RATE_AND_CONVERSION_COST")
        rows.append({
            "provider_id": item["id"],
            "provider_name": item["name"],
            "official_docs": list(item["official_docs"]),
            "review_note": item["review_note"],
            "documented_general_capabilities": documented,
            "capability_gaps_to_investigate": unverified,
            "comparison_priority": ("REVIEW_FIRST" if not unverified
                                    else "REVIEW_WITH_GAPS"),
            "unverified_gates": gates,
            "merchant_eligibility_verified": False,
            "recipient_eligibility_verified": False,
            "country_currency_coverage_verified": False,
            "provider_contract_signed": False,
            "can_charge": False,
            "can_payout": False,
            "ready_for_production": False,
        })
    rows.sort(key=lambda r: (-len(r["documented_general_capabilities"]),
                             r["provider_id"]))
    return {
        "task": 121,
        "reviewed_on": "2026-11-01",
        "request": {
            "merchant_country": merchant_country,
            "merchant_entity": merchant_entity,
            "charge_currency": charge_currency,
            "recipient_country": recipient_country,
            "payout_currency": payout_currency,
            "recipient_type": recipient_type,
            "required_capabilities": sorted(required),
            "cross_border": cross_border,
            "currency_conversion_to_review": fx_needed,
        },
        "candidates": rows,
        "selection": None,
        "status": "CANDIDATE_COMPARISON_ONLY",
        "external_due_diligence_required": True,
        "legal_tax_approval": False,
        "real_money_enabled": False,
        "operating_db_connected": False,
        "provider_api_called": False,
    }
