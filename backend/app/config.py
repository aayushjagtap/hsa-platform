import os

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://hsa:hsa@localhost:55432/hsa",
)

