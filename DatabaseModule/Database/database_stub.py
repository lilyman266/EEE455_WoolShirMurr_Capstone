#class is designed to be inherited by the:
# comms module
# web app
# ground station app ? 
# admin 
# TODO: implement permissions levels for acoustic data#

from abc import ABC, abstractmethod
import psycopg2
from datetime import datetime

HOST = "localhost"
DBNAME = "gs_db"
USER = "postgres"
PASSWORD = "1234"
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
    def add_log(self, type:str, origin:str, data:str):
        pass
    #Add acoustic data to DB
    @abstractmethod
    def add_acoustic_data(self):
        pass
    #Add uplink command to DB
    @abstractmethod
    def add_uplink_command(self):
        pass
    #Add command response to DB
    @abstractmethod
    def add_command_response(self):
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
    
    #Parameters:
    # type: #string: type of log to be inputted. Must be valid in TYPELIST.
    # data: string: the content of the log. Brevity is key to save database space!
    #Returns:
    # type if there is a TypeNotValidError
    # data if there is a DataNotValidError
    # 0 if operation completed without errors
    #Description: 
    # This is a function designed to add a log to the "LOG" database from the Communications module.#
    def add_log(self, type:str, data:str):
        #check if type is valid, if not raise TypeNotValidError and return the type inputted
        if type not in TYPELIST:
            raise TypeNotValidError()
            return type
        #check if data is a string
        if not isinstance(data, str):
            raise DataNotValidError()
            return data
        #open db connection
        conn = psycopg2.connect(host=HOST, dbname=DBNAME, user=USER, password=PASSWORD, port=PORT)
        cursor = conn.cursor()

        #Attempt insertion - ANY ERRORS ARE HANDLED BY POSTGRESQL
        cursor.execute("""INSERT INTO logs (type, origin, data) VALUES (%s, %s, %s);""", (type, self.origin, data))

        #commit changes and close connection
        conn.commit()
        cursor.close()
        conn.close()
        return 0
    
    #Parameters:
    # data: TODO: FIGURE OUT THE NATURE OF THE DATA TO STORE and adjust db and function accordingly!
    #Returns:
    # data if there is a DataNotValidError
    # 0 if operation completed without errors
    #Description: 
    # This is a function designed to add acoustic data to the "acoustic_data" table in the "gs_db" database from the Communications module.#
    def add_acoustic_data(self, data:str):
        #check if data is a string TODO: FIGURE OUT WHAT FORM THIS WILL ACTUALLY TAKE AND ADJUST THE COMMAND/DB ACCORDINGLY!
        if not isinstance(data, str):
            raise DataNotValidError()
            return data
        #open db connection
        conn = psycopg2.connect(host=HOST, dbname=DBNAME, user=USER, password=PASSWORD, port=PORT)
        cursor = conn.cursor()

        #Attempt insertion - ANY ERRORS ARE HANDLED BY POSTGRESQL
        cursor.execute("""INSERT INTO acoustic_data (raw_data) VALUES (%s);""", (data,))

        #commit changes and close connection
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
        #check if data is a string
        if not isinstance(data, str):
            raise DataNotValidError()
            return data
        #open db connection
        conn = psycopg2.connect(host=HOST, dbname=DBNAME, user=USER, password=PASSWORD, port=PORT)
        cursor = conn.cursor()

        #Attempt insertion - ANY ERRORS ARE HANDLED BY POSTGRESQL
        cursor.execute("""INSERT INTO uplink_commands (data) VALUES (%s);""", (data))

        #commit changes and close connection
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
        #check if data is a string
        if not isinstance(data, str):
            raise DataNotValidError()
            return data
        #open db connection
        conn = psycopg2.connect(host=HOST, dbname=DBNAME, user=USER, password=PASSWORD, port=PORT)
        cursor = conn.cursor()

        #Attempt insertion - ANY ERRORS ARE HANDLED BY POSTGRESQL
        cursor.execute("""INSERT INTO downlink_responses (data) VALUES (%s);""", (data))

        #commit changes and close connection
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
        
class WebAppDatabaseStub(DatabaseStub):
    
    def __init__(self):
        super().__init__()
        self.origin = 'web_app'
    
    #Add a log to the DB - NOTE: add_log SHOULD NOT BE IMPLEMENTED FOR WEB APP
    def add_log(self, type:str, data:str):
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
    
    #Read acoustic data from the DB
    #Parameters: 
    # start_time = string: 'YYYY-MM-DD HH:MM:SS+00'
    # end_time = string: 'YYYY-MM-DD HH:MM:SS+00'
    # id: not used for this implementation
    #Returns: List of acoustic data entries#
    def read_acoustic_data(self, start_time:datetime=None, end_time:datetime=None, id:int=None, restricted:bool=None):
        conn = psycopg2.connect(host=HOST, dbname=DBNAME, user=USER, password=PASSWORD, port=PORT)
        cursor = conn.cursor()
        #Function to ensure they are allowed to access the info
        
        #Function to ensure the fields are the right data type
        cursor.execute("""SELECT pg_input_is_valid(%s, timestamptz);""", (start_time))
        if cursor.fetchone() == 'false':
            raise InputNotValidError(f"start time is not valid! Inputted start time: {start_time}")
    
        cursor.execute("""SELECT pg_input_is_valid(%s, timestamptz);""", (end_time))
        if cursor.fetchone() == 'false':
            raise InputNotValidError(f"end time is not valid! Inputted end time: {end_time}")

        clauses = []
        params = {}
        if start_time is not None:
            clauses.append("timestamp>=%(start_time)s")
            params["start_time"] = start_time
        if end_time is not None:
            clauses.append("timestamp<=%(end_time)s")
            params["end_time"] = end_time
        if id is not None:
            clauses.append("id=%(id)s")
            params["id"] = id
        if restricted is not None:
            clauses.append("restricted=%(restricted)s")
            params["restricted"] = restricted

        where = " AND ".join(clauses) if clauses else "FALSE"
        query = f"""SELECT json_agg(row_to_json(t)) * FROM (select * FROM acoustic_data WHERE {where}) t;"""
        cursor.execute(query, params)
        to_return = cursor.fetchall()

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
    