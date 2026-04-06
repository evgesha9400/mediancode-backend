<%doc>
- Parameters:
- api : TemplateApi
- extra_dependencies : list[str] - additional pip dependencies
- extra_dev_dependencies : list[str] - additional dev-only pip dependencies
</%doc>\
[project]
name = "${api.kebab_name}"
version = "${api.version}"
description = "${api.description}"
authors = [
    {name = "${api.author}"}
]
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "uvicorn (>=0.34.0,<1.0.0)",
    "fastapi (>=0.115.0,<1.0.0)"\
% for dep in extra_dependencies:
,
    "${dep}"\
% endfor

]

[dependency-groups]
dev = [
    "httpx (>=0.28.0,<1.0.0)",
    "pyyaml (>=6.0.0,<7.0.0)"\
% for dep in extra_dev_dependencies:
,
    "${dep}"\
% endfor
]

[tool.poetry]
package-mode = false

[build-system]
requires = ["poetry-core>=2.0.0,<3.0.0"]
build-backend = "poetry.core.masonry.api"
