"""Optional PyTorch policy components; install goat-ai[ml] to use them."""

from .behavioral_clone import fit_behavioral_clone
from .checkpoint import load_policy_agent
from .demonstrations import demonstrator_records
from .policy import (
    CardVocabulary,
    DecisionFeatures,
    LegalActionPolicy,
    PolicyAgent,
    encode_decision,
)

__all__ = ["CardVocabulary", "DecisionFeatures", "LegalActionPolicy", "PolicyAgent",
           "demonstrator_records", "encode_decision", "fit_behavioral_clone",
           "load_policy_agent"]
