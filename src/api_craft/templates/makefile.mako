<%doc>
- Template Parameters:
- api: TemplateApi
</%doc>\
.PHONY: install run-local build clean run-container swagger

PROJECT_NAME=${api.snake_name}

install:
	@poetry install

run-local: install
	@PYTHONPATH=src poetry run uvicorn main:app --reload --port 8000

build:
	@docker build -t $(PROJECT_NAME) .

clean:
	-@docker stop $(PROJECT_NAME) 2>/dev/null || true
	-@docker rm $(PROJECT_NAME) 2>/dev/null || true
	-@docker rmi $(PROJECT_NAME) 2>/dev/null || true

run-container: install clean build
	@docker run --name $(PROJECT_NAME) -p 8000:80 -d $(PROJECT_NAME):latest

swagger: install
	@PYTHONPATH=src poetry run python swagger.py
