-- Runs once when the Postgres container is first created.
-- The app uses "hsa"; the test suite uses its own "hsa_test" database.
CREATE DATABASE hsa_test;
