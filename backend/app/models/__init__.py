"""SQLAlchemy ORM models representing database tables."""

# Import all models here so that Alembic's env.py (which imports this package)
# can discover them via Base.metadata for autogenerate migrations.
from app.models.broker import Broker  # noqa: F401
from app.models.customer import Customer  # noqa: F401
from app.models.listing import Listing  # noqa: F401
from app.models.conversation import Conversation  # noqa: F401
from app.models.lead import Lead  # noqa: F401
