-- Review/delivery only; the assistant has not executed these statements.
-- Current direct account has SELECT on cbebg and no ALTER privilege.
-- Execute with an authorized ALTER account. If an ADD fails, restore enable=true.
-- 1. Temporarily disable dynamic partition management for this table.
ALTER TABLE cbebg.ods_tenant00001_t_oms_advertised_sppr SET ("dynamic_partition.enable" = "false");
-- 2. Add the missing historical years; retain all existing partitions.
ALTER TABLE cbebg.ods_tenant00001_t_oms_advertised_sppr ADD PARTITION IF NOT EXISTS p2022 VALUES [('2022-01-01 00:00:00'), ('2023-01-01 00:00:00'));
ALTER TABLE cbebg.ods_tenant00001_t_oms_advertised_sppr ADD PARTITION IF NOT EXISTS p2023 VALUES [('2023-01-01 00:00:00'), ('2024-01-01 00:00:00'));
ALTER TABLE cbebg.ods_tenant00001_t_oms_advertised_sppr ADD PARTITION IF NOT EXISTS p2024 VALUES [('2024-01-01 00:00:00'), ('2025-01-01 00:00:00'));
-- 3. Restore the original dynamic partition setting.
ALTER TABLE cbebg.ods_tenant00001_t_oms_advertised_sppr SET ("dynamic_partition.enable" = "true");
-- 4. Verify p2022 through p2027 and dynamic_partition.enable=true.
SHOW PARTITIONS FROM cbebg.ods_tenant00001_t_oms_advertised_sppr;
SHOW CREATE TABLE cbebg.ods_tenant00001_t_oms_advertised_sppr;
