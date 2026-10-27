"""SQL fragments for Person 2's ``listing`` table, shared by the AI modules.

Kept in a module with no heavy imports so the boundary filter and amenities
service can use them without loading the embedding model.

``location`` is a PostGIS Point (SRID 4326), so ``ST_X`` is the longitude and
``ST_Y`` the latitude. Bedrooms live in the ``rooms`` JSON column (``NULL``
for plots). The expressions below match the backend's expression indexes
(``ix_listing_bedrooms`` and ``idx_listing_location_geog``) character for
character, so Postgres can use those indexes.
"""

# Mirrors VISIBLE_STATUSES in the backend's app/models/listing.py: sold and
# withdrawn listings never appear in customer search.
VISIBLE_STATUS_SQL = "status IN ('available', 'under_offer')"
BEDROOMS_SQL = "(rooms->>'bedrooms')::int"
LAT_SQL = "ST_Y(location)"
LNG_SQL = "ST_X(location)"
