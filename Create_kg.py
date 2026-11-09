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
        # Loop through all possible F1 CSV date formats until one succeeds
        for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                parsed_date = datetime.strptime(val, date_format)
                return Date(parsed_date.year, parsed_date.month, parsed_date.day)
            except ValueError:
                continue # If it fails, move to the next format
        
        # Fallback if a completely broken date is found
        print(f"Warning: Could not parse date format for '{val}'")
        return None
    
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
            
def remove_nulls(properties):
    """Filters out any keys where the value is None to ensure Neo4j omits the property."""
    return {k: v for k, v in properties.items() if v is not None}

def load_drivers(session):
    print("Loading Drivers...")
    for row in read_csv_data("drivers"):
        props = remove_nulls({
            "driverId": clean_val(row["driverId"], "int"),
            "driverRef": clean_val(row["driverRef"]),
            "number": clean_val(row["number"], "int"),
            "code": clean_val(row["code"]),
            "forename": clean_val(row["forename"]),
            "surname": clean_val(row["surname"]),
            "dob": clean_val(row["dob"], "date"),
            "nationality": clean_val(row["nationality"])
        })
        session.run("""
            MERGE (d:Driver {driverId: $props.driverId})
            SET d += $props
        """, props=props)

def load_constructors(session):
    print("Loading Constructors...")
    for row in read_csv_data("constructors"):
        # Map CSV 'name' to 'constructor_name' and 'nationality' to 'constructor_nationality'
        props = remove_nulls({
            "constructorId": clean_val(row["constructorId"], "int"),
            "constructorRef": clean_val(row["constructorRef"]),
            "constructor_name": clean_val(row["name"]), 
            "constructor_nationality": clean_val(row["nationality"])
        })
        session.run("""
            MERGE (c:Constructor {constructorId: $props.constructorId})
            SET c += $props
        """, props=props)

def load_circuits(session):
    print("Loading Circuits...")
    for row in read_csv_data("circuits"):
        # Map CSV 'name' to 'circuit_name', 'location' to 'circuit_loc', etc.
        props = remove_nulls({
            "circuitId": clean_val(row["circuitId"], "int"),
            "circuitRef": clean_val(row["circuitRef"]),
            "circuit_name": clean_val(row["name"]),
            "circuit_loc": clean_val(row["location"]),
            "circuit_country": clean_val(row["country"]),
            "lat": clean_val(row["lat"], "float"),
            "lng": clean_val(row["lng"], "float"),
            "alt": clean_val(row["alt"], "int")
        })
        session.run("""
            MERGE (c:Circuit {circuitId: $props.circuitId})
            SET c += $props
        """, props=props)

def load_seasons(session):
    print("Loading Seasons...")
    for row in read_csv_data("seasons"):
        props = remove_nulls({
            "year": clean_val(row["year"], "int")
        })
        session.run("""
            MERGE (s:Season {year: $props.year})
            SET s += $props
        """, props=props)

def load_status(session):
    print("Loading Statuses...")
    for row in read_csv_data("status"):
        props = remove_nulls({
            "statusId": clean_val(row["statusId"], "int"),
            "status": clean_val(row["status"])
        })
        session.run("""
            MERGE (s:Status {statusId: $props.statusId})
            SET s += $props
        """, props=props)

def load_races(session):
    print("Loading Races...")
    for row in read_csv_data("races"):
        props = remove_nulls({
            "raceId": clean_val(row["raceId"], "int"),
            "year": clean_val(row["year"], "int"),
            "round": clean_val(row["round"], "int"),
            "name": clean_val(row["name"]),
            "date": clean_val(row["date"], "date"),
            "time": clean_val(row["time"]) # Time remains a string
        })
        session.run("""
            MERGE (r:Race {raceId: $props.raceId})
            SET r += $props
        """, props=props)


def link_races(session):
    print("Linking Races to Circuits and Seasons...")
    for row in read_csv_data("races"):
        raceId = clean_val(row["raceId"], "int")
        circuitId = clean_val(row["circuitId"], "int")
        year = clean_val(row["year"], "int")
        
        session.run("""
            MATCH (r:Race {raceId: $raceId})
            MATCH (c:Circuit {circuitId: $circuitId})
            MATCH (s:Season {year: $year})
            MERGE (r)-[:AT_CIRCUIT]->(c)
            MERGE (r)-[:IN_SEASON]->(s)
        """, raceId=raceId, circuitId=circuitId, year=year)

def load_results(session):
    print("Loading Results Fact Nodes & Relationships...")
    for row in read_csv_data("results"):
        props = remove_nulls({
            "resultId": clean_val(row["resultId"], "int"),
            "number": clean_val(row["number"], "int"),
            "grid": clean_val(row["grid"], "int"),
            "position": clean_val(row["position"], "int"),
            "positionText": clean_val(row["positionText"]),
            "positionOrder": clean_val(row["positionOrder"], "int"),
            "points": clean_val(row["points"], "float"),
            "laps": clean_val(row["laps"], "int"),
            "time": clean_val(row["time"]),
            "milliseconds": clean_val(row["milliseconds"], "int"),
            "fastestLap": clean_val(row["fastestLap"], "int"),
            "rank": clean_val(row["rank"], "int"),
            "fastestLapTime": clean_val(row["fastestLapTime"]),
            "fastestLapSpeed": clean_val(row["fastestLapSpeed"], "float")
        })
        
        # Foreign keys for relationships
        driverId = clean_val(row["driverId"], "int")
        raceId = clean_val(row["raceId"], "int")
        constructorId = clean_val(row["constructorId"], "int")
        statusId = clean_val(row["statusId"], "int")

        session.run("""
            MERGE (res:Result {resultId: $props.resultId})
            SET res += $props
            WITH res
            MATCH (d:Driver {driverId: $driverId})
            MATCH (r:Race {raceId: $raceId})
            MATCH (c:Constructor {constructorId: $constructorId})
            MATCH (s:Status {statusId: $statusId})
            MERGE (res)-[:BY_DRIVER]->(d)
            MERGE (res)-[:FOR_RACE]->(r)
            MERGE (res)-[:FOR_CONSTRUCTOR]->(c)
            MERGE (res)-[:HAS_STATUS]->(s)
        """, props=props, driverId=driverId, raceId=raceId, constructorId=constructorId, statusId=statusId)

def load_qualifying(session):
    print("Loading Qualifying Fact Nodes & Relationships...")
    for row in read_csv_data("qualifying"):
        props = remove_nulls({
            "qualifyId": clean_val(row["qualifyId"], "int"),
            "number": clean_val(row["number"], "int"),
            "position": clean_val(row["position"], "int"),
            "q1": clean_val(row["q1"]),
            "q2": clean_val(row["q2"]),
            "q3": clean_val(row["q3"])
        })
        
        driverId = clean_val(row["driverId"], "int")
        raceId = clean_val(row["raceId"], "int")
        constructorId = clean_val(row["constructorId"], "int")

        session.run("""
            MERGE (q:Qualifying {qualifyId: $props.qualifyId})
            SET q += $props
            WITH q
            MATCH (d:Driver {driverId: $driverId})
            MATCH (r:Race {raceId: $raceId})
            MATCH (c:Constructor {constructorId: $constructorId})
            MERGE (q)-[:BY_DRIVER]->(d)
            MERGE (q)-[:FOR_RACE]->(r)
            MERGE (q)-[:FOR_CONSTRUCTOR]->(c)
        """, props=props, driverId=driverId, raceId=raceId, constructorId=constructorId)

def load_pitstops(session):
    print("Loading PitStops Fact Nodes & Relationships...")
    for row in read_csv_data("pit_stops"):
        raceId = clean_val(row["raceId"], "int")
        driverId = clean_val(row["driverId"], "int")
        stop = clean_val(row["stop"], "int")
        
        # Construct the unique eventId string per the milestone requirements
        eventId = f"{raceId}:{driverId}:{stop}"

        props = remove_nulls({
            "eventId": eventId,
            "stop": stop,
            "lap": clean_val(row["lap"], "int"),
            "time": clean_val(row["time"]),
            "duration": clean_val(row["duration"]),
            "milliseconds": clean_val(row["milliseconds"], "int")
        })

        session.run("""
            MERGE (p:PitStop {eventId: $props.eventId})
            SET p += $props
            WITH p
            MATCH (d:Driver {driverId: $driverId})
            MATCH (r:Race {raceId: $raceId})
            MERGE (p)-[:BY_DRIVER]->(d)
            MERGE (p)-[:FOR_RACE]->(r)
        """, props=props, driverId=driverId, raceId=raceId)
if __name__ == "__main__":
    verify_connection()
    
    with driver.session() as session:
        print("--- Starting Phase 1: Entity Nodes ---")
        load_drivers(session)
        load_constructors(session)
        load_circuits(session)
        load_seasons(session)
        load_status(session)
        load_races(session)
        print("--- Phase 1 Complete ---")
        
        print("--- Starting Phase 2: Fact Nodes & Relationships ---")
        link_races(session)
        load_results(session)
        load_qualifying(session)
        load_pitstops(session)
        print("--- Phase 2 Complete ---")
        
    driver.close()