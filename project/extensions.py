import logging
import pytz
from flask_apscheduler import APScheduler
from project.utils.logging_util import load_json

load_json()
logger = logging.getLogger("main")
scheduler = APScheduler()
app_config = None


def db_extensions(app):
    scheduler.init_app(app)
    global app_config
    app_config = app.config_obj
    scheduler._scheduler.timezone = pytz.timezone('UTC')
    scheduler.start()
