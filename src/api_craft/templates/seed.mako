<%doc>
- Template Parameters:
- orm_models: list[TemplateORMModel]
- seed_data: dict[str, dict[str, Any]] - model_name -> {field_name: value}
</%doc>\
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orm_models import (
% for model in orm_models:
    ${model.class_name},
% endfor
)


async def seed_database(session: AsyncSession) -> None:
    """Seed the database with placeholder data. Idempotent."""
% for model in orm_models:
<%
    model_seed = seed_data.get(model.source_model, {})
    # Filter to only fields that exist on the ORM model and are not auto-generated PKs
    orm_field_names = {f.name for f in model.fields if not (f.primary_key and (f.autoincrement or f.uuid_default))}
    seed_fields = {k: v for k, v in model_seed.items() if k in orm_field_names}
%>\
% if seed_fields:
    existing_${model.table_name} = await session.execute(select(${model.class_name}).limit(1))
    if not existing_${model.table_name}.scalars().first():
        session.add_all([
            ${model.class_name}(
% for field_name, value in seed_fields.items():
                ${field_name}=${value.__repr__()},
% endfor
            ),
        ])
% endif
% endfor
    await session.commit()
