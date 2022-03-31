#!/usr/bin/env python3
'''
Rotation 

'''

import config
import os
import sys
import argparse
import psycopg2
import psycopg2.extras

from datetime import datetime
from datetime import timedelta
from shapely import wkt
from scipy.spatial.transform import Rotation as R
import numpy as np
from shapely.geometry import Polygon


num_format = "{:,}".format
class rotation():
    def __init__(self):
        None
    def arr_to_polygon(self,arr):
        return Polygon([(arr[i, 0], arr[i, 1]) for i in range(arr.shape[0])])

    def polygon_to_arr(self,poly):
        """
        Parameters:
            poly: shapely Polygon
        returns
            3D array of long, lat
        """
        return np.array([[x, y, 0] for x, y in poly.boundary.coords])

    def updateAngle(self,connection, osm_id,ogr_fid,angle):
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        sql = f'''
          update ml.msft_model_validations
                set angle = '{angle}'
                where id = {osm_id}
                and ogc_fid = {ogr_fid};
                '''
        cursor.execute(sql)
        connection.commit()
        print (f'''updated osm_id {osm_id} ogr_fid {ogr_fid} angle='{angle}' ''' )

    def calcRotation(self, connection):
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        
        sql = f'''
           select id,ogc_fid, st_astext(m.geom)  geom,st_astext( m.wkb_geometry)wkb_geometry 
            from ml.msft_model_validations m
            where m.angle = ''
           
                '''
        cursor.execute(sql)

        records = cursor.fetchall()
        for row in records:
            id = row['id']
            ogc_fid = row['ogc_fid']
            geom = row['geom']
            wkb_geometry = row['wkb_geometry']
            # original polygon
            original_polygon_wkt = geom.replace('MULTIPOLYGON(((','POLYGON((').replace(')))','))')
            original_polygon = wkt.loads(original_polygon_wkt)
           
            # rotated polygon
            rotated_polygon_wkt = rotated_wkt = wkb_geometry.replace('MULTIPOLYGON(((','POLYGON((').replace(')))','))')
            rotated_polygon = wkt.loads(rotated_polygon_wkt)
           
            # convert polygon coords into N,3 array
            original_polygon_arr = md.polygon_to_arr(original_polygon)
            rotated_polygon_arr = md.polygon_to_arr(rotated_polygon)
            angle = 'Error'
            # estimate rotation
            try:
                rotation_result, _  = R.align_vectors(rotated_polygon_arr, original_polygon_arr)
                estimated_rotation = rotation_result.as_euler('xyz', degrees=True)
                angle = f"{estimated_rotation[2]:0.6f}"           
            except Exception as e:
                angle = e                
            # convert to degrees
            
            md.updateAngle(connection,id,ogc_fid,angle)


argParser = argparse.ArgumentParser(description="Calc")
argParser.add_argument('-H', '--host', action='store', dest='dbHost', default=None, help='Database host FQDN or IP address')
argParser.add_argument('-P', '--port', action='store', dest='dbPort', default=None, help='Database port')
argParser.add_argument('-u', '--user', action='store', dest='dbUser', default=None, help='Database username')
argParser.add_argument('-p', '--password', action='store', dest='dbPass', default=None, help='Database password')
argParser.add_argument('-d', '--database', action='store', dest='dbName', default=None, help='Target database')

args = argParser.parse_args()

"""
Order of precedence for database credentials:
    1. Arguments passed to the program
    2. ENVVAR
    3. Hard-coded values in config.py
"""
database_connection_parameters = dict(
    database = config.DATABASE_NAME if args.dbName == None else args.dbName,
    user = config.DATABASE_USER if args.dbUser == None else args.dbUser,
    password = config.DATABASE_PASSWORD if args.dbPass == None else args.dbPass,
    host = config.DATABASE_HOST if args.dbHost == None else args.dbHost,
    port = config.DATABASE_PORT if args.dbPort == None else args.dbPort,
)
try:
    conn = psycopg2.connect(
        database=database_connection_parameters['database'],
        user=database_connection_parameters['user'],
        password=database_connection_parameters['password'],
        host=database_connection_parameters['host'],
        port=database_connection_parameters['port']
    )
    print("Connection is OK")
except psycopg2.OperationalError as err:
    print("Connection error: Please recheck the connection parameters")
    print("Current connection parameters:")
    database_connection_parameters['password'] = f"{type(database_connection_parameters['password'])}(**VALUE REDACTED**)"
    print(database_connection_parameters)
    sys.exit(1)

beginTime= datetime.now()

md = rotation()

md.calcRotation(conn)

endTime = datetime.now()
timeCost = endTime - beginTime

print( 'Processing time cost is ', timeCost)

print ('All done.')