from flask import Flask

from project.config import config
from project.extensions import db_extensions


def create_app(config_name):
    app = Flask(__name__)
    app.config_name = config_name
    this_config = config.get(config_name)() or config.get('development')()
    app.config.from_object(this_config)
    app.config_obj = this_config
    this_config.init_app(app)
    db_extensions(app)
    config_blueprint(app)
    config_errorhandler(app)
    return app


def config_blueprint(app):
    with app.app_context():
        from project.controllers import FLASKR_BLUEPRINT
        if app.config_name == 'development':
            url_prefix = '/dev'
        else:
            url_prefix = '/prod'
        for blueprint, prefix in FLASKR_BLUEPRINT:
            app.register_blueprint(blueprint, url_prefix=url_prefix + prefix)


def config_errorhandler(app):
    @app.errorhandler(404)
    def page_not_found(e):
        return 'error 404'
