import yaml
import json
from src.main import app

SWAGGER_PATH = "swagger.yaml"


def export():
    """Update swagger file"""
    swagger_json = app.openapi()
    swagger_yaml = yaml.load(json.dumps(swagger_json), Loader=yaml.FullLoader)
    with open(SWAGGER_PATH, "w") as f:
        f.write(yaml.dump(swagger_yaml))
        print("swagger.yaml updated!")


if __name__ == '__main__':
    export()





