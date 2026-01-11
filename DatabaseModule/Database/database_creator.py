################################################################################
#DATABASE CREATOR:
# Author: OCdt Wooltorton, F
# Description: This script is to create a database of the same type that will
# be used in the Audimus ground station. The database will have four tables:
# 1) Logs:
# - timestamp : timetamp [ (p) ] [without time zone] : 8 bytes
# - type : CREATE TYPE mood AS ENUM ('sad', 'ok', 'happy'); : 4 bytes
# - origin (maybe) : CREATE TYPE mood AS ENUM ('sad', 'ok', 'happy'); : 4 bytes
# - data : text : x bytes where x = length of string
# 2) Acoustic Data:
# - timestamp : timetamp [ (p) ] [without time zone] : 8 bytes
# - raw data : bytea : x bytes where x = number of bytes
# 3) Uplink Commands:
# - timestamp : timetamp [ (p) ] [without time zone] : 8 bytes
# - data : text : x bytes where x = length of string
# 4) Downlink Responses:
# - timestamp : timetamp [ (p) ] [without time zone] : 8 bytes
# - data : text : x bytes where x = length of string
# #
import psycopg2

conn = psycopg2.connect(host="localhost", dbname="gs_db", user="postgres", password="1234", port=5432)

cursor = conn.cursor()

#Step 1: create database tables
#Log table:
#requires an enumerated type to store the type of log as well as the origin of the logs
cursor.execute("""CREATE TYPE log_type AS ENUM (
    'update', 
    'warning', 
    'error'
    );""")

cursor.execute("""CREATE TYPE log_origin AS ENUM (
    'gs_app', 
    'comms_mod', 
    'web_app'
    );""")

cursor.execute("""CREATE TABLE IF NOT EXISTS logs (
    id bigserial PRIMARY KEY,
    tz TIMESTAMPTZ NOT NULL DEFAULT now(),
    type log_type NOT NULL,
    origin log_origin NOT NULL,
    data text NOT NULL
    )""")

#acoustic data table:
cursor.execute("""CREATE TABLE IF NOT EXISTS acoustic_data (
    id bigserial PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    restricted bool DEFAULT 1,
    raw_data bytea NOT NULL,
    )""")

#Uplink Commands table:
cursor.execute("""CREATE TABLE IF NOT EXISTS uplink_commands (
    id bigserial PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    data text NOT NULL
    )""")

#Downlink Responses table:
cursor.execute("""CREATE TABLE IF NOT EXISTS downlink_responses (
    id bigserial PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    data text NOT NULL
    )""")

#commit changes
conn.commit()

#close connection
cursor.close()
conn.close()