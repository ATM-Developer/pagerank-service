from project.controllers.base_import import *

hello = Blueprint('hello', __name__)


@hello.route('/', methods=['GET'])
def hello_world():
    return response(ResponseCode.SUCCESS)
