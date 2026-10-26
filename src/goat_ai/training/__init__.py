"""Optional PyTorch policy components; install goat-ai[ml] to use them."""

from .behavioral_clone import fit_behavioral_clone
from .checkpoint import load_policy_agent
from .parent_kl import fit_preferences_with_parent_kl, fit_with_parent_kl
from .policy import (
    CardVocabulary,
    DecisionFeatures,
    LegalActionPolicy,
    PolicyAgent,
    encode_decision,
)

__all__ = ["CardVocabulary", "DecisionFeatures", "LegalActionPolicy", "PolicyAgent",
           "encode_decision", "fit_behavioral_clone", "fit_preferences_with_parent_kl",
           "fit_with_parent_kl",
           "load_policy_agent"]
