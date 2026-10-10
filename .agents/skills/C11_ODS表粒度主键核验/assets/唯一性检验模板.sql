WITH dc AS (
    SELECT {{业务主键字段列表}}, COUNT(*) AS cnt
    FROM {{目标库表}}
    WHERE {{检查范围}}
    GROUP BY {{业务主键字段列表}}
    HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS quality_value
FROM dc;
