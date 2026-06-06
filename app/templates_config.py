"""Shared Jinja2Templates instance — singleton to avoid cache issues."""

import jinja2
from fastapi.templating import Jinja2Templates

# Create a custom environment with cache_size=0 to avoid
# "unhashable type: 'dict'" errors in Jinja2's LruCache.
_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("app/templates"),
    cache_size=0,
)
templates = Jinja2Templates(env=_env)
