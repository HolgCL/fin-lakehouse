-- Adds prior-fiscal-year raw balance-sheet items (for CCC averaging, §6) and prior revenue/
-- net_income (for their YoY trend features) via a per-company window function.
select
    *,
    lag(inventory) over (partition by cik order by fiscal_year) as inventory_prior,
    lag(receivables) over (partition by cik order by fiscal_year) as receivables_prior,
    lag(payables) over (partition by cik order by fiscal_year) as payables_prior,
    lag(revenue) over (partition by cik order by fiscal_year) as revenue_prior,
    lag(net_income) over (partition by cik order by fiscal_year) as net_income_prior
from {{ ref('stg_company_year') }}
