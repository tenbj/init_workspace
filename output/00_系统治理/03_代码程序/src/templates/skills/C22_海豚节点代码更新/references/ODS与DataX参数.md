# ODS与DataX参数

## 先看参数怎样进入模板

本次节点使用自定义JSON，reader为postgresqlreader，writer为doriswriter：querySql的字符串引用 `${sql}`，writer数组为 `"column":[${columns}]`。先读现场完整模板，不假定所有DataX都采用这个结构。

- sql：PG实际查询语义，含大小写双引号标识符；嵌入JSON字符串需要匹配运行器的转义。
- columns：目标字段的JSON数组元素片段，如 `"id","add_time","is_delete"`。此模板的参数值不含外层方括号；不照搬sql转义，不填SQL表达式。
- preSql、postSql、日期、SCD参数：先核对现值和本轮影响，不因不熟悉而改动。

## 输出列与columns

1. 按SELECT最终输出顺序逐列对应writer目标字段，表达式使用实际别名。
2. 新字段同时出现在SQL与columns正确位置：数量、顺序一致，无重复。
3. 保留审计字段和映射，如add_time输出last_updated_dt。别名不等于源列名。
4. 依据实体元数据确认目标列和类型。varchar映射int依赖实际值和用户决策，不是默认规则；当前范围通过不等于历史全部值可转换。
5. 复杂SQL含函数参数、子查询、字符串逗号时，不用简单逗号分割；用可靠解析或逐项核对。SELECT *先确认实际展开顺序。

## 转义表示与SQL语义分别验证

本案例旧成功版本使用单行SQL，四个PG大小写标识符带反斜杠转义。GitLab普通SQL如 `"FBA"`，节点sql参数为 `\"FBA\"`。这里反斜杠是实际参数字符，不是网络JSON再次序列化后的显示层。

1. 检查字符串、注释、美元引号、多语句等结构。只对安全的简单SELECT压缩排版换行；任意SQL机械压缩所有空白会改变字符串/行注释语义。
2. 对确认后的SQL作JSON字符串内容编码，例如JavaScript的 `JSON.stringify(sql).slice(1,-1)`。本例单行编码后8个双引号各带一个转义反斜杠。
3. 验证 `JSON.parse('"' + encoded + '"')` 还原意图执行的SQL；实际模板替换后也应可解析。离线验证用占位值代替连接密钥。
4. 结合Shell/JVM参数替换确认转义层数，优先对照本节点成功版本。不同链路不能盲目套用层数；静态JSON通过仍须真实试跑。
5. 保存后回读后台实际值，检查换行、反斜杠、解码SQL、columns；不能只看input.value，单行控件可能屏蔽持久化换行。
6. 保留PG双引号和大小写，不能删除引号来规避JSON异常。GitLab业务SQL不写海豚运行器专用转义。

## 运行验收

核对StartTime/EndTime、preSql范围、工作流和各节点终态、DataX读取/失败数及Doris加载/过滤数。成功后恢复原定时。增量试跑和历史回填分开记录，425条通过不代表整表历史新字段已补齐。
