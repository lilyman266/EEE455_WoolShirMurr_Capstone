from abc import ABC, abstractmethod
import random
from DatabaseModule.Database.database_stub import WebAppDatabaseStub

db_stub = WebAppDatabaseStub()

class AuthStub(ABC):
    def __init__(self):
        pass
    #NOTE: this should return 0 (user login), 1 (admin login), or 2 (failed login)
    @abstractmethod
    def login_test(self, username, password):
        pass

    @abstractmethod
    def logout(self):
        pass

    @abstractmethod
    def create_account(self, username, password):
        pass

    #NOTE- FOR THE REAL IMPLEMENTATION USE THE TIME TO MAKE A UNIQUE KEY
    @abstractmethod
    def create_key(self, username, password):
        pass

    @abstractmethod
    def validate_key(self, key, account):
        pass
    
class AuthStubUserTable(AuthStub):
    def __init__(self):
        super().__init__()
        self.user_accounts = {}

    #tests to see if the username password combo is correct.
    def login_test(self, username, password):
        auth_status = db_stub.get_user_info(username, password)
        if auth_status == 1:
            self.user_accounts[username] = [password, 0]
        return auth_status

    def logout(self):
        pass

    def create_account(self, username, password):
        pass

    def create_key(self, username, password):
        account = self.user_accounts[username]
        print(account)
        if not account:
            return 0
        if account[0] != password:
            return 0
        # if key hasn't been made, then create one
        if self.user_accounts[username][1] == 0:
            key = random.randint(100000, 999999)
            self.user_accounts[username][1] = key
            print(f"AuthStub: create_key: {key}")
        # if key has been made, make a new key
        else:
            key = self.user_accounts[username][1] = random.randint(100000, 999999)
        return key

    def validate_key(self, key, account):
        print(f"AuthStub: validate_key: {key}")
        test_account = self.user_accounts.get(account)
        print(f"test account is: {test_account}")
        if test_account is None:
            print("returning here")
            return 0
        if int(key) == int(test_account[1]):
            print("AuthStub: valid key")
            return 1
        print("AuthStub: invalid key")
        return 0

class AuthDbStubTest(AuthStub):
    def __init__(self):
        super().__init__()
        self.test_user_accounts = {
            "hi": ["bye", 0],
            "admin": ["admin", 0]
        }
    #TODO: MAKE THIS WORK WITH DATABASE_STUB!
    def login_test(self, uname, password):
        if uname in self.test_user_accounts:
            if password == self.test_user_accounts[uname][0]:
                print("login_test passed")
                return 1
            print("login_test failed")
            return 0
        print("login_test failed")
        return 0

    def create_key(self, username, password):
        account = self.test_user_accounts[username]
        print(account)
        if not account:
            return 0
        if account[0] != password:
            return 0
        #if key hasn't been made, then create one
        if self.test_user_accounts[username][1] == 0:
            key = random.randint(100000, 999999)
            self.test_user_accounts[username][1] = key
            print(f"AuthStub: create_key: {key}")
        #if key has been made, make a new key
        else:
            key = self.test_user_accounts[username][1] = random.randint(100000, 999999)
        return key

    def create_account(self, username, password):
        pass

    def validate_key(self, key, account):
        print(f"AuthStub: validate_key: {key}")
        test_account = self.test_user_accounts.get(account)
        print(f"test account is: {test_account}")
        if test_account is None:
            print("returning here")
            return 0
        if int(key) == int(test_account[1]):
            print("AuthStub: valid key")
            return 1
        print("AuthStub: invalid key")
        return 0

    def logout(self):
        pass
