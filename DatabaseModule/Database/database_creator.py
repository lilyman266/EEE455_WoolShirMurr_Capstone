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
import mysql.connector
from mysql.connector import errorcode
import time

HOST = "localhost"
DBNAME = "audimus"
USER = "Audimus"
PASSWORD = "Audimus"

conn = None
cursor = None

try:
    conn = mysql.connector.connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        database=DBNAME,
    )
    cursor = conn.cursor()
except mysql.connector.Error as err:
    if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
        print("error: access denied")
    elif err.errno == errorcode.ER_BAD_DB_ERROR:
        print("error: database does not exist")
    else:
        print(err)

#Step 1: create database tables
#Log table:
#requires an enumerated type to store the type of log as well as the origin of the logs
# cursor.execute("""CREATE TYPE log_type AS ENUM (
#     'update', 
#     'warning', 
#     'error'
#     );""")

# cursor.execute("""CREATE TYPE log_origin AS ENUM (
#     'gs_app', 
#     'comms_mod', 
#     'web_app'
#     );""")
sql = """
CREATE TABLE IF NOT EXISTS db_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    operation_name TEXT NOT NULL,
    duration_ms DOUBLE NOT NULL,
    success BOOLEAN NOT NULL
);

CREATE TABLE IF NOT EXISTS logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    tz TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    type ENUM('update', 'warning', 'error') NOT NULL,
    origin ENUM('gs_app', 'comms_mod', 'web_app') NOT NULL,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS acoustic_data (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    restricted BOOLEAN DEFAULT TRUE,
    raw_data LONGBLOB NOT NULL,
    content_type VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS uplink_commands (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS downlink_responses (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    username VARCHAR(255) PRIMARY KEY,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_link (
    username VARCHAR(255) NOT NULL,
    acoustic_id BIGINT NOT NULL,
    PRIMARY KEY (username, acoustic_id),
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
    FOREIGN KEY (acoustic_id) REFERENCES acoustic_data(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS user_requests (
    username VARCHAR(255) NOT NULL,
    acoustic_id BIGINT NOT NULL,
    PRIMARY KEY (username, acoustic_id),
    FOREIGN KEY (username) REFERENCES users(username) ON DELETE CASCADE,
    FOREIGN KEY (acoustic_id) REFERENCES acoustic_data(id) ON DELETE CASCADE
);
"""
cursor.execute(sql)
# Only 3 methods needed: create, read and add user requests.
# 
# the format for creating user requests will be:
# 1. add requested dataset to user_requests
#
# the format for reading user requests will be:
# 1. read all requests. Return in JSON format.
# 
# the format for accepting user requests will be: 
# 1. add the reference from user_requests to user_link
# 2. delete from user_requests#

time.sleep(2)
#commit changes
conn.commit()

#close connection
cursor.close()
conn.close()