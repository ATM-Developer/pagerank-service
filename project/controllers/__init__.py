from .sign import bsign
from .assets import assets
from .hello import hello

FLASKR_BLUEPRINT = (
    (hello, '/'),
    (bsign, '/assets'),
    (assets, '/assets'),
)
