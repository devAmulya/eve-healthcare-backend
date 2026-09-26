from slowapi import Limiter
from slowapi.util import get_remote_address

# In-memory storage is sufficient here: rate limiting only needs to survive
# for the life of a single process. Swapping to a shared store (Redis) would
# only matter behind multiple API replicas, which is out of scope here.
limiter = Limiter(key_func=get_remote_address)
