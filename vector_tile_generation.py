import os
import psycopg2
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry, WKTElement
from geoalchemy2.functions import ST_AsMVTGeom, ST_TileEnvelope
import geopandas as gpd
import math



# Set up your PostGIS connection
db_config = {
    'dbname': 'postgres',
    'user': 'postgres',
    'password': 'admin',
    'host': 'localhost',
    'port': '5432'
}

# Connect to the database
connection_string = f"postgresql://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['dbname']}"
engine = create_engine(connection_string)


tricity = gpd.read_postgis(sql="select * from osm.tricity", con=engine);


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)



Session = sessionmaker(bind=engine)
session = Session()

# Define the extent
min_x, min_y, max_x, max_y = tricity.total_bounds # Example extent covering the world

# Define the zoom levels
zoom_levels = list(range(19, 20))  # Example zoom levels from 0 to 17

# Define the SQL query template to fetch geometries for each zoom level
sql_template = '''
    SELECT
        ST_AsMVT(q, 'lines_tricity', 4096, 'geom') as mvt
    FROM (
        SELECT
            ST_AsMVTGeom(
                ST_Transform(geom, 3857),
                ST_TileEnvelope({z}, {x}, {y}),
                4096,
                0,
                true
            ) AS geom,
            *
        FROM
            osm.lines_tricity
        WHERE
            geom && ST_Transform(ST_TileEnvelope({z}, {x}, {y}), 4326)
    ) q;
'''

# Generate vector tiles for the specified extent and zoom levels
for z in zoom_levels:
    min_tile_x, max_tile_y = deg2num(min_y, min_x, z)
    max_tile_x, min_tile_y = deg2num(max_y, max_x, z)
    for x in range(min_tile_x, max_tile_x + 1):
        for y in range(min_tile_y, max_tile_y + 1):
            print(z, x, y)
            sql = sql_template.format(z=z, x=x, y=y)
            result = session.execute(sql).scalar()
            if result:
                tile_path = f"tiles/{z}/{x}"
                os.makedirs(tile_path, exist_ok=True)
                with open(f"{tile_path}/{y}.mvt", "wb") as tile_file:
                    tile_file.write(result)