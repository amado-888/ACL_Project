import csv
from neo4j import GraphDatabase
from datetime import datetime
from neo4j.time import Date
def load_config(filepath="config.txt"):
    """
    Reads config.txt by key, not by line number, to safely ignore 
    the injected DATABASE line from the autograder.
    """
    config = {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line:
                    key, value = line.split("=", 1)
                    config[key.strip()] = value.strip()
        return config
    except FileNotFoundError:
        print(f"Error: {filepath} not found.")
        exit(1)

config = load_config()
URI = config.get("URI")
USERNAME = config.get("USERNAME")
PASSWORD = config.get("PASSWORD")

if not all([URI, USERNAME, PASSWORD]):
    print("Error: Missing URI, USERNAME, or PASSWORD in config.txt")
    exit(1)


driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

def verify_connection():
    try:
        driver.verify_connectivity()
        print("Successfully connected to Neo4j! The Bolt connection is live.")
    except Exception as e:
        print(f"Connection failed: {e}")
        
        
def clean_val(val, cast_type="string"):
    """
    Cleans missing values and casts the data to the strict types 
    required by the milestone schema.
    """
    val = val.strip()
    
    # 1. Handle missing values: omit the property by returning None
    if val == r"\N" or val == "":
        return None
        
    # 2. Cast to the required strict types
    if cast_type == "int":
        return int(val)
    elif cast_type == "float":
        return float(val)
    elif cast_type == "date":
        parsed_date = datetime.strptime(val, "%Y-%m-%d")
        return Date(parsed_date.year, parsed_date.month, parsed_date.day)
    
    return val

def read_csv_data(filename):
    """
    A generator that reads a CSV file and yields each row as a dictionary.
    This prevents memory overload when loading the 26,000+ row results.csv.
    """
    filepath = f"{filename}.csv" # Assuming CSVs are now next to the script
    with open(filepath, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row
if __name__ == "__main__":
    verify_connection()
    driver.close()