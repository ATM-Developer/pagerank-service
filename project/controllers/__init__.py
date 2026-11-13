from .sign import bsign
from .assets import assets
from .hello import hello
from .points_sign import bpoints_sign

FLASKR_BLUEPRINT = (
    (hello, '/'),
    (bsign, '/assets'),
    (assets, '/assets'),
    (bpoints_sign, '/points'),
)
