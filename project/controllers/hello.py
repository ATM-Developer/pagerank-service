from project.controllers.base_import import *
from project.extensions import app_config

hello = Blueprint('hello', __name__)


@hello.route('/', methods=['GET'])
def hello_world():
    logger.info('hello. over')
    return response(ResponseCode.SUCCESS, data={'version': app_config.APP_VERSION})
