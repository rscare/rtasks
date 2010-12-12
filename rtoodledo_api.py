#!/usr/bin/python

class RemoteAPIError(Exception):
    def __init__(self, value):
        self.value = value

class InformationError(Exception):
    def __init__(self, missinginfo):
        self.value = missinginfo

class toodledo:
    """Class to allow interfacing to toodledo.com."""

    _appid = "example"
    _apptoken = "example"
    _token_max_age = 60 * 60 * 4 # In seconds

    def __init__(self, userid, password, token, user = None):
        """Method to initialize the class. Expects a userid (can be None), password, and token."""

        self._userid = userid
        self._password = password
        self._token = token
        self._key = None

        if not(self._userid):
            if not(user): raise InformationError("user or userid")
            self._userid = self.__GetUserID(user)

        self._accountinfo = self.__GetAccountInfo()

    def GetDeletedTasks(self, after = None):
        return self.__TaskAPICall("deleted", {
            "after" : after,
            "key" : self.__key()
            })[1:]

    def GetTasks(self, fields, args = None):
        if fields:
            fields = ','.join(fields)
            args["fields"] = fields
        args["key"] = self.__key()
        tasks = self.__TaskAPICall("get", args)[1:]
        rtasks = []
        for task in tasks:
            if ("folder" in task) and (task['folder'] == "0"): del(task['folder'])
            if ("tag" in task) and (task['tag'].replace(" ", '') == ""): del(task['tag'])
            if ("context" in task) and (task['context'] == "0"): del(task['context'])
            if ("duedate" in task) and (int(task['duedate']) <= 0): del(task['duedate'])
            if ("completed" in task) and (int(task['completed']) <= 0): del(task['completed'])
            rtasks.append(task)
        return rtasks

    def AddTasks(self, tasks):
        import json
        return self.__TaskAPICall("add", {
            "tasks" : json.dumps(tasks),
            "key" : self.__key()
            })

    def EditTasks(self, tasks):
        import json
        return self.__TaskAPICall("add", {
            "tasks" : json.dumps(tasks),
            "key" : self.__key()
            })

    def DeleteTasks(self, tasks):
        import json
        return self.__TaskAPICall("delete", {
            "tasks" : json.dumps([task['id'] for task in tasks]),
            "key" : self.__key()
            })

    def GetContexts(self):
        return self.__ContextAPICall("get", {
            "key" : self.__key()
            })

    def AddContext(self, contextname):
        return self.__ContextAPICall("add", {
            "name" : contextname,
            "key" : self.__key()
            })

    def DeleteContext(self, contextid):
        return self.__ContextAPICall("delete", {
            "id" : contextid,
            "key" : self.__key()
            })

    def GetFolders(self):
        return self.__FolderAPICall("get", {
            "key" : self.__key()
            })

    def AddFolder(self, foldername):
        return self.__FolderAPICall("add", {
            "name" : foldername,
            "key" : self.__key()
            })

    def DeleteFolder(self, folderid):
        return self.__FolderAPICall("delete", {
            "id" : folderid,
            "key" : self.__key()
            })

    def __GetAccountInfo(self):
        rvalue = self.__AccountAPICall("get", {
            "key" : self.__key()
            })

        # Make date values comparable
        for (k, v) in rvalue.items():
            if (k.find("lastedit") != -1) or (k.find("lastdelete") != -1):
                rvalue[k] = int(v)

        return rvalue

    def __GenSig(self, element):
        """Generates application signature."""
        from hashlib import md5
        return md5((element + self._apptoken).encode('utf-8')).hexdigest()

    def __token(self):
        from time import time

        if not(self._token) or ((time() - self._token[1]) >= self._token_max_age):
            self._token  = (self.__AccountAPICall("token", { 
                "userid" : self._userid, 
                "appid" : self._appid, 
                "sig" : self.__GenSig(self._userid)
                })["token"], time())
        return self._token[0]

    def __key(self):
        """Generate general authentication key."""
        from hashlib import md5
        from time import time
        if not(self._key) or not(self._token) or ((time() - self._token[1]) >= self._token_max_age):
            self._key = md5((md5(self._password.encode('utf-8')).hexdigest() + self._apptoken + self.__token()).encode('utf-8')).hexdigest()
        return self._key

    def __GetUserID(self, user):
        """Gets permanent userid -- should only have to be ever used once per account.
        
        This usage is, though, the responsibility of the application, not this class."""

        return self.__AccountAPICall("lookup", {
            "appid" : self._appid,
            "email" : user,
            "pass" : self._password,
            "sig": self.__GenSig(user)
            })["userid"]

    def __TaskAPICall(self, call_name, args):
        return self.__APICall("tasks", call_name, args)

    def __ContextAPICall(self, call_name, args):
        return self.__APICall("contexts", call_name, args)

    def __FolderAPICall(self, call_name, args):
        return self.__APICall("folders", call_name, args)

    def __AccountAPICall(self, call_name, args):
        return self.__APICall("account", call_name, args)

    def __APICall(self, category, call_name, args):
        """Takes a caller name and arguments, returns parsed JSON result of API call."""

        import json
        from urllib.parse import quote_plus
        from urllib.request import urlopen

        url = "http://api.toodledo.com/2/{0}/{1}.php?".format(category, call_name)

        url_args = ''
        for (k, v) in args.items():
            url_args += ";{0}={1}".format(k, quote_plus(str(v), safe = ''))
        url += url_args

        rvalue = json.loads(str(urlopen(url).read(), encoding='utf-8'))

        if "errorCode" in rvalue: raise RemoteAPIError(rvalue["errorDesc"])
        else: return rvalue
