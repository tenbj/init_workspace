-- 查询数据：query_data；实体数据：table_data。
-- 制作模板：交付前替换全部双花括号占位符，不可直接执行本文件。
-- 数据CTE定义需包含完整WITH依赖及query_data、table_data，最后一个CTE以)结束。
-- 交付注释按C15规范写实际日期/范围、异常日期组计数含义及必要特殊口径；删除制作提示。
-- 查看差异日期明细：仅将最后COUNT(*) AS quality_value换为*，保留FROM dc；输出日期、两侧行数及差额。
{{数据CTE定义}}
, query_count_result AS (
    SELECT {{查询日期表达式}} AS check_date
         , COUNT(*) AS query_count
    FROM query_data
    GROUP BY {{查询日期表达式}}
)
, table_count_result AS (
    SELECT {{实体日期表达式}} AS check_date
         , COUNT(*) AS table_count
    FROM table_data
    GROUP BY {{实体日期表达式}}
)
, check_dates AS (
    SELECT check_date FROM query_count_result
    UNION
    SELECT check_date FROM table_count_result
)
, daily_comparison AS (
    SELECT d.check_date
         , COALESCE(q.query_count, 0) AS query_count
         , COALESCE(t.table_count, 0) AS table_count
    FROM check_dates d
    LEFT JOIN query_count_result q ON d.check_date <=> q.check_date
    LEFT JOIN table_count_result t ON d.check_date <=> t.check_date
)
, dc AS (
    SELECT check_date, query_count, table_count
         , query_count - table_count AS row_difference
    FROM daily_comparison
    WHERE query_count <> table_count
)
SELECT COUNT(*) AS quality_value
FROM dc;
