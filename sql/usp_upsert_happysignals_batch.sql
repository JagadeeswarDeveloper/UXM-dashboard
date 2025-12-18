CREATE PROCEDURE [ExpNXT].[usp_upsert_happysignals_batch]
    @json_data NVARCHAR(MAX)
AS
BEGIN
    SET NOCOUNT ON;

    MERGE [ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS] AS target
    USING (
        SELECT * FROM OPENJSON(@json_data)
        WITH (
            load_date DATE,
            survey_id VARCHAR(100),
            respondent_email VARCHAR(100),
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
            region VARCHAR(255),
            channel VARCHAR(255),
            service_ticket_type VARCHAR(255),
            enterprise_class VARCHAR(255),
            burnout_risk_score DECIMAL(18,2),
            company VARCHAR(255),
            top_company VARCHAR(255),
            sub_company VARCHAR(255),
            created_date DATETIME
        )
    ) AS source
    ON (target.survey_id = source.survey_id)
    WHEN NOT MATCHED THEN
        INSERT (load_date, survey_id, respondent_email, ticket_id, happiness_score, lost_time_minutes, factors, comment, translated_comment, department, location, country, role, region, channel, service_ticket_type, enterprise_class, burnout_risk_score, company, top_company, sub_company, created_date)
        VALUES (source.load_date, source.survey_id, source.respondent_email, source.ticket_id, source.happiness_score, source.lost_time_minutes, source.factors, source.comment, source.translated_comment, source.department, source.location, source.country, source.role, source.region, source.channel, source.service_ticket_type, source.enterprise_class, source.burnout_risk_score, source.company, source.top_company, source.sub_company, source.created_date);
END
GO
