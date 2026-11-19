-- 10 exploratory queries (Sprint 1 deliverable D-04). Run: sqlite3 data/nifty100.db < docs/exploratory_queries.sql
SELECT 'companies', COUNT(*) FROM companies;
SELECT 'rows per table', 'pl', COUNT(*) FROM profitandloss UNION ALL SELECT 'rows per table','bs',COUNT(*) FROM balancesheet UNION ALL SELECT 'rows per table','cf',COUNT(*) FROM cashflow;
SELECT company_id, COUNT(*) yrs FROM profitandloss GROUP BY 1 ORDER BY yrs LIMIT 10;                                -- shortest P&L history
SELECT fy, COUNT(*) FROM profitandloss GROUP BY fy ORDER BY fy;                                                     -- year distribution
SELECT id FROM companies WHERE id NOT IN (SELECT company_id FROM balancesheet);                                    -- companies with no balance sheet (SBIN)
SELECT SUM(sales IS NULL), SUM(net_profit IS NULL), SUM(eps IS NULL), SUM(dividend_payout IS NULL) FROM profitandloss; -- null counts
SELECT year, COUNT(*) FROM balancesheet WHERE year NOT LIKE '%-03' GROUP BY year;                                   -- non-March year ends
SELECT broad_sector, COUNT(*) FROM sectors GROUP BY 1 ORDER BY 2 DESC;                                              -- sector mix
SELECT peer_group_name, COUNT(*) FROM peer_groups GROUP BY 1;                                                       -- peer group sizes
SELECT c.id, 2024 - COUNT(d.year) AS missing_reports FROM companies c LEFT JOIN documents d ON d.company_id = c.id GROUP BY c.id ORDER BY 2 DESC LIMIT 10;
