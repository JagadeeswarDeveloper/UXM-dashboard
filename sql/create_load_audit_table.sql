IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'ExpNXT')
BEGIN
    EXEC('CREATE SCHEMA ExpNXT')
END
GO

IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[ExpNXT].[load_audit]') AND type in (N'U'))
BEGIN
    CREATE TABLE [ExpNXT].[load_audit](
        [audit_id] [int] IDENTITY(1,1) NOT NULL,
        [source_file] [varchar](255) NOT NULL,
        [rows_read] [int] DEFAULT 0,
        [rows_inserted] [int] DEFAULT 0,
        [rows_skipped] [int] DEFAULT 0,
        [rows_failed] [int] DEFAULT 0,
        [start_ts] [datetime] DEFAULT GETUTCDATE(),
        [end_ts] [datetime] NULL,
        [status] [varchar](50) DEFAULT 'STARTED', -- STARTED, COMPLETED, FAILED
        [error_message] [varchar](max) NULL,
        PRIMARY KEY CLUSTERED ([audit_id] ASC)
    )
END
GO
