# Define period types
from enum import Enum

PERIOD_TYPE = ["Unlimited", "Daily", "Hourly", "Monthly"]
UNLIMITED = "Unlimited"

# Define the default rate limit for unlimited access
NO_RATE_LIMIT = {"period": UNLIMITED, "rate": None}


class APIAccessType(Enum):
    # User-facing API access types
    FULL_ACCESS = "full_access"
    CHAT = "chat"
    ASSISTANTS = "assistants"
    FILE_UPLOAD = "file_upload"
    SHARE = "share"
    DUAL_EMBEDDING = "dual_embedding"
    # non user facing ones
    API_KEY = "api_key"
    ARTIFACTS = "artifacts"
    ADMIN = "admin"
    DATA_DISCLOSURE = "data-disclosure"
    EMBEDDING = "embedding"
