import duckdb
con = duckdb.connect('test.duckdb')

con.execute('CREATE TABLE IF NOT EXISTS sales (region TEXT, amount DOUBLE)')
con.execute('DELETE FROM sales')
con.execute("INSERT INTO sales VALUES ('EU', 1200.0), ('US', 2300.0), ('APAC', 850.0), ('EU', 450.0), ('US', 1100.0)")
con.close()
print("test.duckdb created")        