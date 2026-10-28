from enum import Enum
class RiskLevel(str, Enum):
    NORMAL = "NORMAL"
    OBSERVATION = "OBSERVATION"
    SUSPICIOUS = "SUSPICIOUS"
    HIGH_RISK = "HIGH_RISK"
    SECURITY_ALERT = "SECURITY_ALERT"
