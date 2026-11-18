-- 制作提示：按C15监控注释规范补齐实际业务键中文含义、范围及特殊限制，交付前删除本行并替换全部占位符。
-- 结果为重复键组数；一组3行计1组。NULL组合参与分组，单条空键不单独告警。
-- 查看重复键明细：仅将最后COUNT(*) AS quality_value换为*，保留FROM dc；返回业务键及每组行数cnt，不是组内全部原始记录。
WITH dc AS (
    SELECT {{业务主键字段列表}}, COUNT(*) AS cnt
    FROM {{目标库表}}
    WHERE {{检查范围}}
    GROUP BY {{业务主键字段列表}}
    HAVING COUNT(*) > 1
)
SELECT COUNT(*) AS quality_value
FROM dc;
