-- ====================================================================
-- Data Transfer Script: master → DB_Nexthink
-- Run this in SQL Server Management Studio or Azure Data Studio
-- ====================================================================

-- Connect to: dbsustainability.database.windows.net
-- You can run this from either master or DB_Nexthink database

USE master;
GO

-- Step 1: Verify data exists in master
PRINT '=== Checking data in master ===';
SELECT 'RAW_HAPPYSIGNALS_SURVEYS' as TableName, COUNT(*) as RowCount
FROM [master].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]
UNION ALL
SELECT 'RAW_ESG_METRICS', COUNT(*)
FROM [master].[ExpNXT].[RAW_ESG_METRICS];
GO

-- Step 2: Transfer HappySignals data
PRINT '=== Transferring HappySignals data ===';
INSERT INTO [DB_Nexthink].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]
SELECT * 
FROM [master].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS] src
WHERE NOT EXISTS (
    SELECT 1 
    FROM [DB_Nexthink].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS] dst
    WHERE dst.survey_id = src.survey_id
);
PRINT CONCAT('Transferred ', @@ROWCOUNT, ' HappySignals rows');
GO

--Step 3: Transfer EPEAT/ESG data
PRINT '=== Transferring ESG Metrics data ===';
INSERT INTO [DB_Nexthink].[ExpNXT].[RAW_ESG_METRICS]
SELECT *
FROM [master].[ExpNXT].[RAW_ESG_METRICS] src
WHERE NOT EXISTS (
    SELECT 1
    FROM [DB_Nexthink].[ExpNXT].[RAW_ESG_METRICS] dst
    WHERE dst.device_model = src.device_model
    AND dst.epeat_rating = src.epeat_rating
    AND dst.load_date = src.load_date
);
PRINT CONCAT('Transferred ', @@ROWCOUNT, ' ESG Metrics rows');
GO

-- Step 4: Verify data in DB_Nexthink
PRINT '=== Verifying data in DB_Nexthink ===';
SELECT 'RAW_HAPPYSIGNALS_SURVEYS' as TableName, COUNT(*) as RowCount
FROM [DB_Nexthink].[ExpNXT].[RAW_HAPPYSIGNALS_SURVEYS]
UNION ALL
SELECT 'RAW_ESG_METRICS', COUNT(*)
FROM [DB_Nexthink].[ExpNXT].[RAW_ESG_METRICS];
GO

PRINT '=== Transfer Complete ===';
