-- Gold metrics, one row per company-year (docs/PROJECT_BRIEF.md §6). Every ratio's formula is
-- cited in a comment next to it. Divide-by-zero -> null, and the metric name is recorded in
-- null_metric_flags (never a silent number, per §1.6).
--
-- Scope note: revenue_real_yoy (CPI-deflated growth) and break_even are out of scope for v1 per
-- §6 -- no CPI seed table exists yet and no fixed/variable cost split is available from XBRL.
-- Skipped, not fabricated.

with base as (
    select * from {{ ref('int_company_year_with_prior') }}
),

metrics as (
    select
        cik,
        entity_name,
        fiscal_year,
        revenue,
        net_income,
        revenue_prior,
        net_income_prior,

        -- Liquidity
        case when current_liabilities != 0
            then current_assets / current_liabilities end                    as current_ratio,
        case when current_liabilities != 0
            then (current_assets - inventory) / current_liabilities end      as quick_ratio,
        case when current_liabilities != 0
            then cash / current_liabilities end                              as cash_ratio,
        current_assets - current_liabilities                                 as working_capital,

        -- Cash conversion cycle: DIO = inventory/cogs*365, DSO = receivables/revenue*365,
        -- DPO = payables/cogs*365, CCC = DIO + DSO - DPO. Uses the average of opening/closing
        -- balance where a prior year exists, else the closing balance alone.
        case when cogs != 0
            then coalesce((inventory + inventory_prior) / 2, inventory) / cogs * 365 end
            as dio,
        case when revenue != 0
            then coalesce((receivables + receivables_prior) / 2, receivables) / revenue * 365 end
            as dso,
        case when cogs != 0
            then coalesce((payables + payables_prior) / 2, payables) / cogs * 365 end
            as dpo,

        -- Solvency / capital structure
        short_term_debt + long_term_debt                                     as total_debt,
        (short_term_debt + long_term_debt) - cash                            as net_debt,
        case when total_assets != 0
            then equity / total_assets end                                   as equity_ratio,
        case when equity != 0
            then total_liabilities / equity end                              as debt_to_equity,
        case when total_liabilities != 0
            then (short_term_debt + long_term_debt) / total_liabilities end
            as interest_bearing_debt_share,

        -- Efficiency & profitability
        case when total_assets != 0
            then revenue / total_assets end                                  as asset_turnover,
        case when revenue != 0
            then gross_profit / revenue end                                  as gross_margin,
        case when revenue != 0
            then operating_income / revenue end                              as operating_margin,
        case when revenue != 0
            then net_income / revenue end                                    as net_margin,

        -- Quality & normalization
        case when total_assets != 0
            then goodwill / total_assets end                                 as goodwill_to_assets,
        equity - goodwill                                                    as equity_ex_goodwill,
        net_income + coalesce(goodwill_impairment, 0)                        as normalized_net_income,

        list_filter(
            [
                case when current_liabilities = 0 then 'current_ratio' end,
                case when current_liabilities = 0 then 'quick_ratio' end,
                case when current_liabilities = 0 then 'cash_ratio' end,
                case when cogs = 0 then 'dio' end,
                case when revenue = 0 then 'dso' end,
                case when cogs = 0 then 'dpo' end,
                case when total_assets = 0 then 'equity_ratio' end,
                case when equity = 0 then 'debt_to_equity' end,
                case when total_liabilities = 0 then 'interest_bearing_debt_share' end,
                case when total_assets = 0 then 'asset_turnover' end,
                case when revenue = 0 then 'gross_margin' end,
                case when revenue = 0 then 'operating_margin' end,
                case when revenue = 0 then 'net_margin' end,
                case when total_assets = 0 then 'goodwill_to_assets' end
            ],
            x -> x is not null
        ) as null_metric_flags

    from base
),

metrics_with_prior as (
    select
        m.*,
        lag(dso) over (partition by cik order by fiscal_year)          as dso_prior,
        lag(dio + dso - dpo) over (partition by cik order by fiscal_year) as ccc_prior,
        lag(gross_margin) over (partition by cik order by fiscal_year) as gross_margin_prior,
        lag(net_debt) over (partition by cik order by fiscal_year)     as net_debt_prior
    from metrics m
)

select
    cik,
    entity_name,
    fiscal_year,
    current_ratio,
    quick_ratio,
    cash_ratio,
    working_capital,
    dio,
    dso,
    dpo,
    dio + dso - dpo                                                       as ccc,
    total_debt,
    net_debt,
    equity_ratio,
    debt_to_equity,
    interest_bearing_debt_share,
    asset_turnover,
    gross_margin,
    operating_margin,
    net_margin,
    goodwill_to_assets,
    equity_ex_goodwill,
    normalized_net_income,

    -- Trend features (YoY, § 6)
    case when revenue_prior is not null and revenue_prior != 0
        then (revenue - revenue_prior) / revenue_prior end                 as revenue_yoy,
    case when net_income_prior is not null and net_income_prior != 0
        then (net_income - net_income_prior) / net_income_prior end        as net_income_yoy,
    case when dso_prior is not null and dso_prior != 0
        then (dso - dso_prior) / dso_prior end                             as dso_yoy,
    case when ccc_prior is not null and ccc_prior != 0
        then ((dio + dso - dpo) - ccc_prior) / ccc_prior end               as ccc_yoy,
    case when gross_margin_prior is not null and gross_margin_prior != 0
        then (gross_margin - gross_margin_prior) / gross_margin_prior end  as gross_margin_yoy,
    case when net_debt_prior is not null and net_debt_prior != 0
        then (net_debt - net_debt_prior) / net_debt_prior end              as net_debt_yoy,

    null_metric_flags

from metrics_with_prior
