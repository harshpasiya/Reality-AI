$env:PGPASSWORD = 'postgres'
$psql = 'C:\Program Files\PostgreSQL\17\bin\psql.exe'

Write-Host "Creating extensions..."
& $psql -U postgres -h 127.0.0.1 -d reality_ai -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS vector;"
Write-Host "Extensions done."
