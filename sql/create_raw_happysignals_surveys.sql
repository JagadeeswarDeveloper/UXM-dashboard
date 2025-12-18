IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'ExpNXT')
BEGIN
    EXEC('CREATE SCHEMA ExpNXT')
END
GO

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]') AND type in (N'U'))
BEGIN
    CREATE TABLE ExpNXT.RAW_HAPPYSIGNALS_SURVEYS (
        load_date DATE,
        survey_id VARCHAR(100),
        respondent_email VARCHAR(100), -- Join Key
        ticket_id VARCHAR(100),
        happiness_score DECIMAL(18,2),
        lost_time_minutes INT,
        factors VARCHAR(MAX),
        comment VARCHAR(MAX),
        translated_comment VARCHAR(MAX),
        department VARCHAR(255),
        location VARCHAR(255),
        country VARCHAR(255),
        role VARCHAR(255),
        region VARCHAR(255), -- Added V2
        channel VARCHAR(255), -- Added V2
        service_ticket_type VARCHAR(255),
        enterprise_class VARCHAR(255),
        burnout_risk_score DECIMAL(18,2),
        company VARCHAR(255), -- Added V2
        top_company VARCHAR(255), -- Added V2
        sub_company VARCHAR(255), -- Added V2
        created_date DATETIME
    );
END
GO
