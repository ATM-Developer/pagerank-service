from flask_cors import CORS
from project import create_app


config_name = "development"
app = create_app(config_name)
from project import jobs

CORS(app, supports_credentials=True, resources=r'/*')

if __name__ == '__main__':
    print('>>>>> Starting Pagerank Node Server Decentralized <<<<<')
    app.run('0.0.0.0', 5001, threaded=True)
    print('Done')
