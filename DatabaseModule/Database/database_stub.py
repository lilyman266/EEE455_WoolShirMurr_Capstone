#class is designed to be inherited by the:
# comms module
# web app
# ground station app ? 
# admin #

from abc import ABC, abstractmethod
import psycopg2
from datetime import datetime
import mysql.connector


HOST = "localhost"
DBNAME = "gs_db"
USER = "AudimusGroundStation"
PASSWORD = "Ecemysql2026"
PORT = 5432
TYPELIST = ['update', 'warning', 'error']

class TypeNotValidError(Exception):
    """Exception raised for if a type is not valid"""
    pass

class DataNotValidError(Exception):
    """Exception raised for if data is not valid"""
    pass

class InputNotValidError(Exception):
    """Exception raised for if function input is not valid"""
    pass

class DatabaseStub(ABC):

    def __init__(self):
        pass

    #Add log to DB
    @abstractmethod
    def add_log(self, priority:str, origin, destination, description:str):
        pass
    #Add acoustic data to DB
    @abstractmethod
    def add_acoustic_data(self, data:str):
        pass
    #Add uplink command to DB
    @abstractmethod
    def add_uplink_command(self, data:str):
        pass
    #Add command response to DB
    @abstractmethod
    def add_command_response(self, data:str):
        pass
    #Add a user request to user_requests table
    @abstractmethod
    def add_user_request(self, user:str, start_time:str, end_time:str):
        pass
    #ADMIN ONLY: Accept a user request
    @abstractmethod
    def accept_user_request(self, user:str, request_id):
        pass
    #ADMIN ONLY: read all user requests. Returns in json format.
    @abstractmethod
    def read_user_requests(self):
        pass
    @abstractmethod
    def get_user_info(self, user:str, passwd:str):
        pass
    #Read a log from the DB
    @abstractmethod
    def read_log(self, start_time=None, end_time=None, id=None, type=None, origin=None):
        pass
    #Read acoustic data from the DB
    @abstractmethod
    def read_acoustic_data(self, start_time=None, end_time=None, id=None, restricted=None):
        pass
    #Read uplink commands from the DB (not required for this implementation)
    @abstractmethod
    def read_uplink_commands(self, start_time=None, end_time=None, id=None):
        pass
    #Read command responses from the DB (not required for this implementation)
    @abstractmethod
    def read_command_responses(self, start_time=None, end_time=None, id=None):
        pass
        
class CommsModDatabaseStub(DatabaseStub):
    
    def __init__(self):
        super().__init__()
        self.origin = 'comms_mod'

    #DESCRIPTION: adds log to database
    # INPUTS: type: description
    # - priority: string: UPDATE, WARNING, ERROR, etc. Provides an idea of the nature of hte log.
    # - origin: string: process or server ip if needed.
    # - destination: string: receiving process or server ip if needed.
    # - description: more info for the log.
    # RETURNS:
    # - 0 : everything worked!
    # - 1: database doesn't exist
    # - 2: access denied
    # - 3: other error#
    def add_log(self, priority: str, origin, destination, description: str):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        query = """
                INSERT INTO logs (priority, origin, destination, timestamp, description)
                VALUES (%s, %s, %s, %s, %s)
                """
        try:
            cursor.execute(query, (priority, origin, destination, datetime.now(), description))
        except:
            return 3
        conn.commit()
        cursor.close()
        conn.close()
        return 0

    # DESCRIPTION: adds acoustic data to the database
    # INPUTS: type: description
    # - priority: string: UPDATE, WARNING, ERROR, etc. Provides an idea of the nature of hte log.
    # - origin: string: process or server ip if needed.
    # - destination: string: receiving process or server ip if needed.
    # - description: more info for the log.
    # RETURNS:
    # - 0 : everything worked!
    # - 1: database doesn't exist
    # - 2: access denied
    # - 3: other error#
    def add_acoustic_data(self, data:str):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        query = """
                INSERT INTO acoustic_data (timestamp, restricted, raw_data)
                VALUES (%s, %s, %s)
                """
        try:
            cursor.execute(query, (datetime.now(), 1, data))
        except:
            return 3
        conn.commit()
        cursor.close()
        conn.close()
        return 0

    #Parameters:
    # data: string: the content of the log. Brevity is key to save database space!
    #Returns:
    # data if there is a DataNotValidError
    # 0 if operation completed without errors
    #Description: 
    # This is a function designed to add uplink commands in string form to the "uplink_commands" table in the "gs_db" database from the Communications module.#
    def add_uplink_command(self, data:str):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        query = """
                INSERT INTO uplink_commands (timestamp, data) VALUES (%s, %s)
                """
        try:
            cursor.execute(query, (datetime.now(), data))
        except:
            return 3
        conn.commit()
        cursor.close()
        conn.close()
        return 0

    #Parameters:
    # data: string: the content of the log. Brevity is key to save database space!
    #Returns:
    # data if there is a DataNotValidError
    # 0 if operation completed without errors
    #Description: 
    # This is a function designed to add responses to uplink commands to the "downlink_responses" table in the "gs_db" database from the Communications module.#
    def add_command_response(self, data:str):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        query = """
                INSERT INTO downlink_responses (timestamp, data) VALUES (%s, %s)
                """
        try:
            cursor.execute(query,  (datetime.now(), data))
        except:
            return 3
        conn.commit()
        cursor.close()
        conn.close()
        return 0

    #Read a log from the DB - NOTE: read_log SHOULD NOT BE IMPLEMENTED FOR COMMUNICAITONS MODULE
    def read_log(self, start_time=None, end_time=None, id=None, type=None, origin=None):
        pass
    #Read acoustic data from the DB - NOTE: read_acoustic_data SHOULD NOT BE IMPLEMENTED FOR COMMUNICAITONS MODULE
    def read_acoustic_data(self, start_time=None, end_time=None, id=None, restricted=None):
        pass
    #Read uplink commands from the DB  - NOTE: read_uplink_commands SHOULD NOT BE IMPLEMENTED FOR COMMUNICAITONS MODULE
    def read_uplink_commands(self, start_time=None, end_time=None, id=None):
        pass
    #Read command responses from the DB  - NOTE: read_command_responses SHOULD NOT BE IMPLEMENTED FOR COMMUNICAITONS MODULE
    def read_command_responses(self, start_time=None, end_time=None, id=None):
        pass
    def add_user_request(self, user: str, start_time: str, end_time: str):
        pass
    # ADMIN ONLY: Accept a user request
    def accept_user_request(self, user: str, request_id):
        pass
    # ADMIN ONLY: read all user requests. Returns in json format.
    def read_user_requests(self):
        pass
    def get_user_info(self, user:str, passwd:str):
        pass
        
class WebAppDatabaseStub(DatabaseStub):
    
    def __init__(self):
        super().__init__()
        self.origin = 'web_app'
    
    #Add a log to the DB - NOTE: add_log SHOULD NOT BE IMPLEMENTED FOR WEB APP
    def add_log(self, priority:str, origin, destination, description:str):
        pass
    
    #Add acoustic data to the DB - NOTE: add_acoustic_data SHOULD NOT BE IMPLEMENTED FOR WEB APP
    def add_acoustic_data(self, data:str):
        pass

    #Add uplink command to the DB - NOTE: add_uplink_command SHOULD NOT BE IMPLEMENTED FOR WEB APP
    def add_uplink_command(self, data:str):
        pass
    
    #Add command responses to the DB - NOTE: add_command_response SHOULD NOT BE IMPLEMENTED FOR WEB APP
    def add_command_response(self, data:str):
        pass

    #Read a log from the DB
    def read_log(self, start_time=None, end_time=None, id=None, type=None, origin=None):
        pass
    
    
    #Read data from a specific user
    def read_user_data(self, user=None):
        if user is None:
            return

        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        cursor.execute("""
        SELECT COALESCE(
            JSON_ARRAYAGG(JSON_OBJECT(
                'id', a.id,
                'timestamp', a.timestamp,
                'restricted', a.restricted,
                'raw_data', a.raw_data
            )),
            JSON_ARRAY()
        ) AS rows
        FROM user_link l
        JOIN acoustic_data a ON a.id = l.acoustic_id
        WHERE l.username = %s;
        """, (user,))
        to_return = cursor.fetchall()[0][0] 
        conn.commit()
        cursor.close()
        conn.close()
        print(f"database stub says : {to_return}")
        
        return to_return

    #Read acoustic data from the DB
    #Parameters: 
    # start_time = string: 'YYYY-MM-DD HH:MM:SS+00'
    # end_time = string: 'YYYY-MM-DD HH:MM:SS+00'
    # id: not used for this implementation
    #Returns: List of acoustic data entries#
    def read_acoustic_data(self, start_time:datetime=None, end_time:datetime=None, my_id:str=None, restricted:str=None, user:str=None):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        if my_id == "admin" and restricted == "admin":
            print("Got here")
            cursor.execute("""
                            SELECT COALESCE(
                                JSON_ARRAYAGG(JSON_OBJECT(
                                    'id', a.id,
                                    'timestamp', a.timestamp,
                                    'restricted', a.restricted,
                                    'raw_data', a.raw_data
                                )),
                                JSON_ARRAY()
                            ) AS rows
                            FROM (SELECT * FROM acoustic_data) a;""")
            #commit changes and close connection
        else:
            clauses = []
            params = []
            if start_time != None:
                clauses.append("timestamp>=%s")
                params.append(start_time)
            if end_time != None:
                clauses.append("timestamp<=%s")
                params.append(end_time)
            if my_id != None:
                clauses.append("id=%s")
                params.append(my_id)
            if restricted != None:
                clauses.append("restricted=%s")
                params.append(restricted)

            where = " AND ".join(clauses) if clauses else "FALSE"
            query = f"""
                        SELECT COALESCE(
                            JSON_ARRAYAGG(JSON_OBJECT(
                                'id', a.id,
                                'timestamp', a.timestamp,
                                'restricted', a.restricted,
                                'raw_data', a.raw_data
                            )),
                            JSON_ARRAY()
                        ) AS rows
                        FROM (SELECT * FROM acoustic_data WHERE {where}) a;"""
            cursor.execute(query, tuple(params))

        to_return = cursor.fetchall()
        to_return = to_return[0][0]
        #commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()
        return to_return
    
    #Read uplink commands from the DB
    def read_uplink_commands(self, start_time=None, end_time=None, id=None):
        pass
    
    #Read command responses from the DB
    def read_command_responses(self, start_time=None, end_time=None, id=None):
        pass

    def add_user_request(self, user: str, start_time: str, end_time: str):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        cursor.execute("""SELECT id FROM acoustic_data WHERE timestamp BETWEEN %s AND %s AND restricted = True;""", (start_time, end_time))
        ids = [r[0] for r in cursor.fetchall()]

        for data_id in ids:
            cursor.execute("""INSERT IGNORE INTO user_requests (username, acoustic_id) 
                              VALUES (%s, %s)""",
                           (user, data_id))

        # commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()
        return 0

    # ADMIN ONLY: Accept a user request
    def accept_user_request(self, user: str, request_id):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        cursor.execute("""INSERT IGNORE INTO user_link (username, acoustic_id)
                    SELECT username, acoustic_id
                    FROM user_requests
                    WHERE username = %s AND acoustic_id = %s;""", (user, request_id))
        inserted = cursor.rowcount

        if inserted != 0:
            cursor.execute("""DELETE FROM user_requests
                        WHERE username = %s AND acoustic_id = %s;""", (user, request_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            return 1  # accepted!

        # commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()

        return 0

    # ADMIN ONLY: read all user requests. Returns in json format.
    def read_user_requests(self):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        cursor.execute("""
                       SELECT COALESCE(
                            JSON_ARRAYAGG(JSON_OBJECT(
                                'username', a.username,
                                'acoustic_id', a.acoustic_id
                            )),
                            JSON_ARRAY()
                        ) AS rows
                        FROM user_requests a;""")
        to_return = cursor.fetchall()[0]
        print(to_return)

        # commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()
        return to_return

    def get_user_info(self, user:str, passwd:str):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        cursor.execute("""SELECT 1 FROM users WHERE username = %s AND password = %s;""", (user, passwd))
        row = cursor.fetchone()

        # commit changes and close connection
        cursor.close()
        conn.close()

        return 0 if row is None else 1
    
    def create_user(self, user:str, passwd:str):
        try:
            conn = mysql.connector.connect(
                user=USER,
                database=DBNAME,
                host=HOST,
                password=PASSWORD,
            )
            cursor = conn.cursor()
        except mysql.connector.Error as err:
            if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
                return 2
            elif err.errno == errorcode.ER_BAD_DB_ERROR:
                return 1
            else:
                return 3

        cursor.execute("""SELECT 1 FROM users WHERE username = %s;""", (user,))
        row = cursor.fetchone()
        if row is None:
            cursor.execute("""INSERT INTO users (username, password) VALUES (%s,%s)""", (user, passwd))
    
        # commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()

        return 0 if row is not None else 1
# #For each function:
# conn = psycopg2.connect(host="localhost", dbname="gs_db", user="postgres", password="1234", port=5432)

# cursor = conn.cursor()

# #Do stuff ////////////////////

# #commit changes
# conn.commit()

# #close connection
# cursor.close()
# conn.close()


#FOR TESTING ONLY
if __name__ == "__main__":
    stub = CommsModDatabaseStub()
    stub.add_log(type="update", data="boooo")
    
