{#
  Hand-rolled in place of dbt-utils.accepted_range to keep the project dependency-free and
  reproducible from a cold `git clone` with no `dbt deps` network fetch (docs/PROJECT_BRIEF.md
  §3 "local-first, zero-cost to run").
#}
{% test accepted_range(model, column_name, min_value=none, max_value=none) %}

select *
from {{ model }}
where {{ column_name }} is not null
{% if min_value is not none %}
  and {{ column_name }} < {{ min_value }}
{% endif %}
{% if max_value is not none %}
  and {{ column_name }} > {{ max_value }}
{% endif %}

{% endtest %}
