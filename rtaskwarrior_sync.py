#!/usr/bin/python

from rtoodledo_api import toodledo,RemoteAPIError

class TaskWarriorSync(toodledo):
    """Class that inherits from toodledo class in order to properly sync taskwarrior with toodledo.com."""

    def __init__(self, userid, password, tasksfile, compfile, cachefile, user = None):
        """Initializes a class for a synchronization of data. UserID can be None."""

        self._remotefoldersmod = False
        self._remotecontextsmod = False
        self._remotetasksmod = False
        self._remotetasksdel = False

        self._remotefolders = []
        self._remotecontexts = []

        self._tasksfile = tasksfile
        self._compfile = compfile
        self._cachefile = cachefile

        self._token = None

        self._prevaccountinfo = None
        self._lastsync = None
        self._userid = userid

        self.__ReadCacheFile()

        self._appid = 'rtaskwarriorsync'
        self._apptoken = 'api4d04652570d20'
        toodledo.__init__(self, userid, password, self._token, user)

        if self._prevaccountinfo:
            if self._accountinfo['lastedit_task'] > self._prevaccountinfo['lastedit_task']:
                self._remotetasksmod = True
            if self._accountinfo['lastdelete_task'] > self._prevaccountinfo['lastdelete_task']:
                self._remotetasksdel = True
            if self._accountinfo['lastedit_folder'] > self._prevaccountinfo['lastedit_folder']:
                self._remotefoldersmod = True
            if self._accountinfo['lastedit_context'] > self._prevaccountinfo['lastedit_context']:
                self._remotecontextsmod = True
    
    def Sync(self):
        """Procedure to actually initiate synchronization."""

        from time import time

        sync_start = time()
        useful_fields = ['folder', 'context', 'tag', 'duedate', 'priority']

        # Get a list of local tasks
        try:
            ltasks = self.__ParseTWFile(self._tasksfile)
        except IOError:
            ltasks = []
        try:
            ctasks = self.__ParseTWFile(self._compfile)
        except IOError:
            ctasks = []

        # Upload any new tasks
        ntasks = [self.__TWToToodledoTask(task) for task in ltasks if ('toodledoid' not in task)]
        if ntasks: 
            newids = toodledo.AddTasks(self, ntasks)
            newids = dict([[task['title'], task['id']] for task in newids])

            # Set their toodledo id's
            for i in range(len(ltasks)):
                if ltasks[i]['description'] in newids:
                    ltasks[i]['toodledoid'] = newids[ltasks[i]['description']]
                    ltasks[i]['entry'] = time()

        # Upload edited tasks
        if self._lastsync:
            ntasks = [self.__TWToToodledoTask(task) for task in ltasks if (task['entry'] > self._lastsync) and (task['entry'] < sync_start)]
            if ntasks: toodledo.EditTasks(self, ntasks)
            # Completed tasks
            if ctasks:
                ntasks = [self.__TWToToodledoTask(task) for task in ctasks if (task['entry'] > self._lastsync) and ('toodledoid' in task) and (task['entry'] < sync_start)]
                if ntasks: toodledo.EditTasks(self, ntasks)

        # Download new tasks and edited tasks if needed
        if not(self._lastsync) or self._remotetasksmod:
            ntasks = []
            if self._lastsync: ntasks = toodledo.GetTasks(self, useful_fields, {"modafter" : self._lastsync})
            else: ntasks = toodledo.GetTasks(self, useful_fields, {"comp" : 0})
            lids = [task['toodledoid'] for task in ltasks] # By this point, everyone should have an id
            # Outright add new tasks
            ltasks.extend([self.__ToodledoToTWTask(task, use_uuid = True) for task in ntasks if (task['id'] not in lids)])
            # Remotely edited tasks
            etasks = [self.__ToodledoToTWTask(task, use_uuid = True) for task in ntasks if (task['id'] in lids)]
            for task in etasks:
                tindex = lids.index(task['toodledoid']) # Lids should maintain order
                ltasks[tindex] = task

        # Download list of deleted tasks
        if self._remotetasksdel:
            dtasks = toodledo.GetDeletedTasks(self, self._lastsync)
            lids = [task['toodledoid'] for task in ltasks]
            for task in dtasks:
                if task['id'] in lids:
                    tindex = lids.index(task['id'])
                    del(ltasks[tindex])

        # Write new information to TW File
        self.__WriteTWFile(ltasks, self._tasksfile)

        # Write out cache file
        self.__WriteCacheFile()

    def __ReadCacheFile(self):
        """Reads cache file from last synchronization if it exists/contains information."""

        from os.path import isfile
        import pickle

        if not(isfile(self._cachefile)): return 1
        with open(self._cachefile, 'rb') as cfile:
            if self._userid != pickle.load(cfile): return 1
            self._token = pickle.load(cfile)
            self._prevaccountinfo = pickle.load(cfile)
            self._remotefolders = pickle.load(cfile)
            self._remotecontexts = pickle.load(cfile)
            self._lastsync = pickle.load(cfile)

    def __WriteCacheFile(self):
        """Writes information to the cache file for later program run."""
        import pickle
        from time import time
        
        with open(self._cachefile, 'wb') as cfile:
            pickle.dump(self._userid, cfile)
            pickle.dump(self._token, cfile)
            pickle.dump(self._accountinfo, cfile)
            pickle.dump(self._remotefolders, cfile)
            pickle.dump(self._remotecontexts, cfile)
            pickle.dump(int(time()), cfile)

    def __WriteTWFile(self, ltasks, filename):
        """Write local taskwarrior file"""
        
        with open(filename, 'w') as TFILE:
            for task in ltasks:
                TFILE.write('[')
                line = ''
                for (k, v) in task.items():
                    if v != None:
                        if (k == 'tags'): v = ','.join(v)
                        line += '{0}:"{1}" '.format(k, str(v).replace('"', "'").replace(':', ';'))
                TFILE.write(line[:-1])
                TFILE.write(']\n')

    def __ParseTWFile(self, filename):
        """Parse local taskwarrior file."""

        from os.path import isfile
        if not(isfile(filename)):
            raise IOError(0, "File does not exist", filename)

        with open(filename, 'r') as TFILE:
            retlist = [self.__ParseTWTask(task) for task in TFILE]

        return retlist

    def __ParseTWTask(self, task):
        """Parses a single local task."""
        import re
        tlist = [l for l in re.split(r'(\w+:"[^"]*")', task)[1:-1] if l.replace(' ', '')]
        tdict = dict([re.split(r'(\w+):"(.*)"', l)[1:3] for l in tlist])
        if 'due' in tdict: tdict['due'] = int(float(tdict['due']))
        if 'entry' in tdict: tdict['entry'] = int(float(tdict['entry']))
        if 'toodledoid' in tdict: tdict['toodledoid'] = int(tdict['toodledoid'])
        if 'tags' in tdict: tdict['tags'] = [tag for tag in tdict['tags'].replace(' ', '').split(',') if tag != '']
        return tdict

    def __TWToToodledoTask(self, task):
        """Returns a toodledo-compatible task from a taskwarrior task."""
        toodletask = {}
        if 'toodledoid' in task: toodletask['id'] = task['toodledoid']
        toodletask['title'] = task['description']
        if 'tags' in task:
            tlist = task['tags']
            context = [tag for tag in tlist if tag[0] == '@'] # Get first context
            if context: 
                context = context[0]
                del(tlist[tlist.index(context)])
                toodletask['context'] = self.__TWToToodleContext(context)
            if (tlist): toodletask['tag'] = ','.join(tlist)
        if 'project' in task: toodletask['folder'] = self.__TWToToodleFolder(task['project'])
        if 'due' in task: toodletask['duedate'] = int(float(task['due']))
        if 'priority' in task: toodletask['priority'] = self.__TWToToodlePriority(task['priority'])
        if task['status'] == 'completed': toodletask['completed'] = task['entry']
        return toodletask

    def __ToodledoToTWTask(self, task, use_uuid = False):
        """Returns a taskwarior-compatible task from a toodledo task."""
        from time import time
        from uuid import uuid4
        twtask = {}
        twtask['toodledoid'] = task['id']
        twtask['description'] = task['title']
        if 'duedate' in task: twtask['due'] = int(float(task['duedate']))
        if 'context' in task:
            twtask['tags'] = [self.__ToodleToTWContext(task['context'])]
            if 'tag' in task:
                twtask['tags'].extend([t.strip() for t in task['tag'].split(',')])
        if 'tag' in task:
            twtask['tags'] = [t.strip() for t in task['tag'].split(',')]
        if 'folder' in task:
            twtask['project'] = self.__ToodleToTWFolder(task['folder'])
        if 'priority' in task:
            twtask['priority'] = self.__ToodleToTWPriority(task['priority'])
        if 'completed' in task:
            twtask['status'] = "completed"
        else:
            twtask['status'] = "pending"
        twtask['entry'] = time()
        if use_uuid: twtask['uuid'] = uuid4()
        return twtask

    def __TWToToodlePriority(self, priority):
        """Converts taskwarrior priorities to toodledo priorities."""

        if priority == None: return 0
        if priority == 'L': return 1
        if priority == 'M': return 2
        if priority == 'H': return 3

    def __ToodleToTWPriority(self, priority):
        """Converts toodledo priority to one compatible with taskwarrior"""
        priority = int(priority)

        if priority == -1: return None
        if priority == 0: return None
        if priority == 1: return 'L'
        if priority == 2: return 'M'
        if priority == 3: return 'H'

        return None

    def __TWToToodleFolder(self, folder):
        """Converts taskwarrior folder name to an id compatible with toodledo."""
        
        if self._remotefoldersmod or not(self._remotefolders):
            self._remotefolders = toodledo.GetFolders(self)
            self._remotefoldersmod = False

        matched_folders = [f['id'] for f in self._remotefolders if f['name'] == folder]
        if len(matched_folders) == 1:
            return matched_folders[0]
        else:
            new_folder = toodledo.AddFolder(self, folder)[0]
            self._remotefolders.append(new_folder)
            return new_folder

    def __ToodleToTWFolder(self, folderid):
        """Converts toodledo folder id to a folder name compatible with taskwarrior."""

        if self._remotefoldersmod or not(self._remotefolders):
            self._remotefolders = toodledo.GetFolders(self)
            self._remotefoldersmod = False

        return [folder['name'] for folder in self._remotefolders if folder['id'] == folderid][0]

    def __TWToToodleContext(self, context):
        """Converts taskwarrior context to an id compatible with toodledo."""

        context = context[1:]
        if self._remotecontextsmod or not(self._remotecontexts):
            self._remotecontexts = toodledo.GetContexts(self)
            self._remotecontextsmod = False

        matched_contexts = [context['id'] for context in self._remotecontexts if context['name'] == context]
        if len(matched_contexts) == 1:
            return matched_contexts[0]
        else:
            new_context =  toodledo.AddContext(self, context)[0]['id']
            self._remotecontexts.append(new_context)
            return new_context

    def __ToodleToTWContext(self, contextid):
        """Converts toodledo context id to a taskwarrior compatible context."""
        if self._remotecontextsmod or not(self._remotecontexts):
            self._remotecontexts = toodledo.GetContexts(self)
            self._remotecontextsmod = False
        
        return "@" + [context['name'] for context in self._remotecontexts if context['id'] == contextid][0]

    def UserID(self):
        return self._userid

if __name__ == '__main__':
    # Defaults
    from os.path import expanduser,isfile
    taskfile = expanduser('~/.task/pending.data')
    compfile = expanduser('~/.task/completed.data')
    cachefile = expanduser('~/.task/rtoodledo.cache')

    configfile = expanduser('~/.rtoodledo.conf')

    rpass_name = ''
    userid = None
    if not(isfile(configfile)):
        print("For now, must use rpass for passwords...")
        rpass_name = input("rpass account name: ")

    else:
        import configparser
        config = configparser.ConfigParser()
        config.read(configfile)
        rpass_name = config.get('credentials', 'rpass_name')
        userid = config.get('credentials', 'user_id')

    from rpass import rpass
    account = rpass()
    acinfo = account.entries[rpass_name]

    try:
        tw = TaskWarriorSync(userid, acinfo['pass'], taskfile, compfile, cachefile, acinfo['user'])
        tw.Sync()
    except RemoteAPIError as e:
        print(e.value)

    import configparser
    config = configparser.ConfigParser()
    config.add_section('credentials')
    config.set('credentials', 'rpass_name', rpass_name)
    config.set('credentials', 'user_id', tw.UserID())
    with open(configfile, 'w') as CONF:
        config.write(CONF)
