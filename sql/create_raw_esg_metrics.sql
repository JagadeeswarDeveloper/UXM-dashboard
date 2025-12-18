IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'ExpNXT')
BEGIN
    EXEC('CREATE SCHEMA ExpNXT')
END
GO

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[ExpNXT].[RAW_ESG_METRICS]') AND type in (N'U'))
BEGIN
    CREATE TABLE ExpNXT.RAW_ESG_METRICS (
        load_date DATE,
        serial_number VARCHAR(100), -- Join Key
        device_model VARCHAR(255),
        on_time_seconds INT,
        idle_time_seconds INT,
        off_time_seconds INT,
        energy_consumption_kwh DECIMAL(18,4),
        co2_emissions_kg DECIMAL(18,4),
        energy_star_rating VARCHAR(50),
        epeat_rating VARCHAR(50),
        manufacturing_kg_co2 INT,
        lifecycle_kg_co2 INT,
        cpu_power_rating DECIMAL(18,2), -- Added V2
        display_power_rating DECIMAL(18,2), -- Added V2
        battery_capacity VARCHAR(50), -- Added V2
        material_composition VARCHAR(MAX) -- Added V2
    );
END
GO
