from .client import MailGoat, MailGoatAPIError, MailGoatError, MailGoatNetworkError
from .models import Message
from .batch import BatchError, BatchSummary
from .profiles import MailProfile, ProfileError

__all__ = [
    "MailGoat",
    "MailGoatError",
    "MailGoatAPIError",
    "MailGoatNetworkError",
    "Message",
    "BatchError",
    "BatchSummary",
    "MailProfile",
    "ProfileError",
]
