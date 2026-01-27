from abc import ABC, abstractmethod
import random

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
    def validate_key(self, key):
        pass

class AuthDbStubTest(AuthStub):
    def __init__(self):
        super().__init__()
        self.test_user_accounts = {
            "hi": "bye"
        }

    def login_test(self, uname, password):
        if uname in self.test_user_accounts:
            if password == self.test_user_accounts[uname]:
                return 1
            return 0
        return 0

    def create_key(self, username, password):
        key = random.randint(100000, 999999)
        self.test_user_accounts[username] = f"{self.test_user_accounts[username]}:{key}"
        print(f"AuthStub: create_key: {key}")
        return key

    def create_account(self, username, password):
        pass

    def validate_key(self, key):
        print(f"AuthStub: validate_key: {key}")
        for user in self.test_user_accounts:
            if key == self.test_user_accounts[user].split(":")[1]:
                return 1
        return 0

    def logout(self):
        pass
