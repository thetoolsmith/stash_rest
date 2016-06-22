'''

TODO: need to classify some of this.


examples:

At first run on you local machine, run --setstash. This will prompt for stash admin credentials and a passphrase
for you to remember. This will be needed for subsequent calls using this utility without passing the credentials.
The credentials entered at first run will be stored in encrypted for in ~.stashcfg

first run set local credentials store:
  
  python stash-rest.py --setstash

create simple pr:

  python stash-rest.py --project MYPROJ --repo MYREPO --createpr --title "test pr" --from feature/thefeature --to master

query open pull requests:

  python stash-rest.py --project MYPROJ --repo MYREPO --list prs --output list

  --output can also be json or pretty-json

get available repository hooks in formatted json:

  python stash-rest.py --project MYPROJ --repo MYREPO --hooks --output json

enable repository hook:

  python stash-rest.py --project MYPROJ --repo MYREPO --sethook "Stash Webhook to Jenkins=enabled"

disable repository hook:

  python stash-rest.py --project MYPROJ --repo MYREPO --sethook "Stash Webhook to Jenkins=disabled"

list repository branches:

  python stash-rest.py --project MYPROJ --repo MYREPO --list branches"


'''

import os
import traceback
import sys
import simplejson as j
import subprocess
import argparse
import json
import exceptions

from pr_template import PRTemplate

from stash import Stash

from sets import Set
from getpass import getpass
from simplecrypt import encrypt, decrypt

stash_user = None 
pretty = False
output = 'string'
stash_server = None
branch = None
hookname = None
hookstatus = None
from_branch = None
to_branch = None

session = Stash()

def initialize():

  print '\ninitializing...'

  cfg = os.environ.get('HOME') + '/.stashcfg'

  global stash_server 
  global stash_user

  _pass = None
  _user = None

  if (stash_server):

    _user = raw_input("username: ")
    _pass = getpass("password: ")

    print "remember this passphrase!!"
    _keyword = getpass("passphrase: ") 

    _hash = encrypt(_keyword, _pass.encode('utf8'))

    f = open(cfg,'w')
    f.write('STASH_HOST={0}'.format(stash_server))
    f.write('STASH_USER={0}\n'.format(_user))
    f.write('STASH_PASS={0}\n'.format(_hash))
    f.close
  else:
    if os.path.exists(cfg):
      f = open(cfg,'r')
      for l in f:
        if 'STASH_HOST' in l:
          stash_server = l.split('=')[1]
        if 'STASH_USER' in l:
          _user = l.split('=')[1]
        if 'STASH_PASS' in l:
          _pass = l.split('=')[1]

      _keyword = getpass("passphrase: ")

      if (_pass) and (_user) and (stash_server):
        stash_user = '{0}:{1}'.format(_user.strip(),decrypt(_keyword,_pass.strip()))
      else:
        raise 'ERROR: Missing stashcfg, run again with "--setstash" [example: http://your.server:port] one time'
      return

    else:
      raise 'ERROR: Missing stashcfg, run again with "--setstash" [example: http://your.server:port] one time'
 

def _print_pretty_json(data):

  _out = json.dumps(data, sort_keys=True, indent=2, separators=(',', ': '))

  print _out

  return _out 

def process_data_chunk(data=None):

		x = 0

		while x < len(data['values']):

				if (output == 'json'):
						_print_pretty_json(data['values'][x])

				if (output == 'string'):
						print data['values'][x]

				x+=1

		completed = True

		if (pretty):
				return _print_pretty_json(data)

		return data

def process_query(uri=None):

  '''
  This function assumes paginated for all queries.

  so '?' must be on the uri when passed in here.

  value url params are: 
    &start=xx, query will start at 0 if not passed in.
    &limit=xx, default is 25 items per page. you can set this limit higher or lower.
               *** NOTE THAT THE STASH API MIGHT AND MOSTLY DOES SET HARD LIMITS ON RETURNS. FOR EXAMPLE commits has A 30 MAX.
  '''

  if (not uri):
    return None

  ictr = 0 # change url if paginated result set, and loop on pages builing full has from chunks

  completed = False


  '''
  weird behavior with stash api
  when passing start=50 for example (any number) in the chrome browser, the api returns items 50 thru 74
  http://stash.myorg.com/rest/api/1.0/projects/MYPROJ/repos/MYREPO/commits?until=refs/heads/master&start=50
  and the start value is returned as 50 and nextPageStart=75. This is expected

  but...
  when running that same url in a curl command, items 0 thru 24 are returned and the start=is set to 0 and nextPageStart=25.
  
  different result when pasting in the browser!!!!

  So, we have to page through all items in a loop instead of making targeted queries for specific item sets such as 75-100 

  could also add &limit=xx to up the per page return from 25 to xx
  '''

  _all = {}
  all_ctr = 0

  # set url path, query string separator 
  if not (uri[len(uri) -1] == '?'):
    uri = '{0}?'.format(uri)

  while (not completed):

    _get = subprocess.Popen('curl -u {0} --insecure --silent \'{1}&start={2}\''.format(stash_user, uri, ictr), shell=True, stdout=subprocess.PIPE )

    _output = _get.communicate()[0]

    chunk = None

    chunk = j.loads(_output)

    #print "next start", chunk['nextPageStart']

    try:

						if (len(chunk) > 0):
								ctr = 0
								while ctr < len(chunk['values']):

										_all[all_ctr] = chunk['values'][ctr]
										ctr+=1
										all_ctr+=1

								if chunk['isLastPage']:
										completed = True
								else:
										ictr = int(chunk['nextPageStart'])
						else:
								completed = True


    except Exception as e:
      exc_type, exc_value, exc_traceback = sys.exc_info()
      traceback.print_exception(exc_type, exc_value, exc_traceback, limit = 3, file = sys.stdout)
      raise RuntimeError("Processing failed.")

  print '\nTotal:', len(_all), '\n'

  #example enum if commits 
  #ctr = 0
  #while ctr < len(_all):
  #  print _all[ctr]['id'], _all[ctr]['author']['name']
  #  ctr+=1

  return 0, _all

def process_hook(uri=None, status=None):

  if ((not uri) or (not status)):
    raise "Required parameter is empty."

  try:

    if 'enabled' in status:
      _put = subprocess.Popen('curl -X PUT -u {0} --insecure --silent \'{1}/enabled\''.format(stash_user, uri), shell=True, stdout=subprocess.PIPE )

    if 'disabled' in status:
     
      _put = subprocess.Popen('curl -X DELETE -u {0} --insecure --silent \'{1}/enabled\''.format(stash_user, uri), shell=True, stdout=subprocess.PIPE )

    _output = _put.communicate()[0]

    return _output

  except Exception as e:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit = 3, file = sys.stdout)
    raise RuntimeError("Processing failed.")

def get_pulls():

  if ((not session.project) or (not session.repo)):
    raise "Missing parameter."

  prs = "http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos/{1}/pull-requests?".format(project, session.repository)

  retcode, data = process_query(uri=prs)

  if retcode == 1: 
    raise ValueError("Get failed!")
 
  if (data):
    return data
  return

def get_repos():

  if (not session.project):
    raise "Missing project parameter."

  print '\nRepos for project {0}\n'.format(session.project)

  repos = "http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos?".format(session.project)

  retcode, data = process_query(uri=repos)

  if retcode == 1: 
    raise "Get failed!"
 
  if (data):
    return data
  return

def get_projects():

  projects = "http://stash.MYORG.com/rest/api/1.0/projects?"

  print '\nProjects\n'

  retcode, data = process_query(uri=projects)

  if ((retcode == 1) or (not (data))):
    raise "Get projects failed!"
 
  return data

 
def get_branches():

  if ((not session.repository) or (not session.project)):
    raise "empty param"

  print '\nBranches for repo {0} in project {1}\n'.format(session.repository, session.project)

  branches = "http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos/{1}/branches?".format(session.project, session.repository)

  retcode, data = process_query(uri=branches)

  if ((retcode == 1) or (not (data))):
    raise "Get branches failed!"
 
  return data

def create_pull_request(fromfile=None, data=None):

  if ((not fromfile) and (not data)):
    raise ValueError ("Must specify data block or \@file")

  if (data):
    uri = "\'http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos/{1}/pull-requests\' -H \"Content-Type: application/json\" -d \'{2}\'".format(session.project, session.repository, data)
  else:
    uri = "\'http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos/{1}/pull-requests\' -H \"Content-Type: application/json\" --data-binary \"@{2}\"".format(session.project, session.repository, fromfile)

  try:

    _put = subprocess.Popen('curl -X POST -u {0} --insecure --silent {1}'.format(stash_user, uri), shell=True, stdout=subprocess.PIPE )

    _output = _put.communicate()[0]

    return _output

  except Exception as e:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    traceback.print_exception(exc_type, exc_value, exc_traceback, limit = 3, file = sys.stdout)
    raise RuntimeError("Create Pull Request failed.")

 

def generate_pr(src=None, dest=None, title=None):

  '''
  Create instance of pr template and replace holder values.
  Return data, pass data=data to create_pull_request()
  '''

  prt = PRTemplate()

  return prt.open_request(repo=session.repository, project=session.project, source=src, dest=dest, title=title)



def set_hook(key=None, status='enabled'):

  if ((not session.repository) or (not session.project) or (not key)):
    raise "Required parameter is empty."

  print '\nSetting Hook {0} to {1} for repo {2} in project {3}\n'.format(key,status,session.repository, session.project)

  hooks = "http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos/{1}/settings/hooks/{2}".format(session.project, session.repository, key)

  retcode = process_hook(uri=hooks, status=status)
  
  return 0


def get_hooks():

  if ((not session.repository) or (not session.project)):
    raise "empty param"

  print '\nHook config for repo {0} in project {1}\n'.format(session.repository, session.project)

  hooks = "http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos/{1}/settings/hooks?".format(session.project, session.repository)

  retcode, data = process_query(uri=hooks)

  if ((retcode == 1) or (not (data))):
    raise "Get hooks failed!"
 
  return data


def get_commits(output=None):

  if ((not session.repository) or (not session.project)):
    raise "empty param"

  print 'Commits for repo {0} in project {1}'.format(session.repository, session.project)

  # must be in this format or without until=xxxxx, the default repo branch will be used.
  # http://stash.MYORG.com/rest/api/1.0/projects/MYPROJ/repos/MYREPO/commits?until=refs/heads/feature/US64439

  if (branch):
    commits = "http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos/{1}/commits?limit=80&until=refs/heads/{2}".format(session.project, session.repository, branch)
  else:
    #default branch
    commits = "http://stash.MYORG.com/rest/api/1.0/projects/{0}/repos/{1}/commits?limit=40".format(session.project, session.repository)

  retcode, data = process_query(uri=commits)

  if ((retcode == 1) or (not (data))): 
    raise "Get commits failed!"
 
  return data

def get_commit_branch(commit=None):
  '''
  this method is very slow. it's called once form each commit id in a list of commits, looking for the branch commited on.
  the stash api does not allow constructed uri to point to specific branches. 
  you pass in the ?until=ref/../.../branchname url paramter and get a list of all commits, then call this for each 
  looking to match the desired branch.
  '''
  if (not commit):
    return None

  commit_branch = "http://stash.MYORG.com/rest/branch-utils/1.0/projects/{0}/repos/{1}/branches/info/{2}".format(session.project, session.repository, commit)

  _get = subprocess.Popen('curl -u {0} --insecure --silent {1}'.format(stash_user, commit_branch), shell=True, stdout=subprocess.PIPE )

  _output = _get.communicate()[0]
  chunk = j.loads(_output)

  #print "returning branch....this is slooooowwwww."  
  return chunk['values'][0]['displayId']


''' ------------------- MAIN ENTRY ----------------------- '''
if __name__ == "__main__":

  parser = argparse.ArgumentParser()

  parser.add_argument(
				'--repo',
				required=False,
				help="Valid stash repo name",
				default=None)

  parser.add_argument(
				'--list',
				required=False,
    metavar="OBJECT",
				help='Valid objects/json to list: projects | repos | branches | prs',
				default=None)

  parser.add_argument(
				'--project',
				required=False,
				help="Valid stash project name",
				default=None)

  parser.add_argument(
				'--commits',
				required=False,
    help="repo and project param needed.",
    action='store_true')

  parser.add_argument(
				'--branch',
				required=False,
    metavar="BRANCHNAME (commit filter)",
    help="Valid branch filter used in --commits query.")

  parser.add_argument(
				'--hooks',
				required=False,
    help="Gets list of hooks available on a repository",
				action='store_true')

  parser.add_argument(
				'--sethook',
				required=False,
    metavar="(ENABLED | DISABLED)",
				help='format: valid hook name=status. Status options (enable | disable). Use --hooks to get a list available hooks.')

  parser.add_argument(
				'--createpr',
				required=False,
				help='Create a new pull request. --title --from --to required.',
    action='store_true')

  parser.add_argument(
				'--title',
				required=False,
    metavar="PULL_REQUEST_TITLE",
				help='title of new pull request',
    default='new pull')

  parser.add_argument(
				'--from',
				required=False,
    metavar="BRANCH",
				help='from repo branch for pull request')

  parser.add_argument(
				'--to',
				required=False,
    metavar="BRANCH",
				help='to repo branch for new pull request')

  parser.add_argument(
				'--output',
				required=False,
    metavar="FORMAT",
				help='return/print type output [list (default) | json | pretty json | off]',
    default='list')

  parser.add_argument(
				'--setstash',
				required=False,
				help='Initial set of stash server to connect to. You will be asked for username, password (hidden), and passphrase as well.\nRun once first time on your local machine.\nYour passphrase will be used to crypt and decrypt the stash user password, so remember it.',
    action='store_true')

  cmdargs = vars(parser.parse_args())


  ''' SET GLOBAL PROJECT AND REPO '''
  if (cmdargs['repo']):
    session.repository = cmdargs['repo']

  if (cmdargs['branch']):
    branch = cmdargs['branch']

  if (cmdargs['project']):
    session.project = cmdargs['project']

  if (cmdargs['setstash']):
    stash_server = cmdargs['setstash']

  if (cmdargs['sethook']):
    hookname = cmdargs['sethook'].split('=')[0]
    hookstatus = cmdargs['sethook'].split('=')[1]
    if ((not hookstatus == 'enabled') and (not hookstatus == 'disabled')):
      raise "Hook status must be \'enabled or disabled\'"

  if (cmdargs['createpr']):
    if ((not cmdargs['from']) or (not cmdargs['to'])):
      raise NameError ("When creating new pull request, --from and --to are required")

    from_branch = cmdargs['from']
    to_branch = cmdargs['to']


  # always init
  initialize()

  print '\nstash host = {0}'.format(stash_server)
 
  if (cmdargs['output'] == 'pretty-json'):
    pretty = True
    
  output = cmdargs['output']

  if (cmdargs['list']):
    if 'repos' in cmdargs['list']:
      if not session.project:
        raise "-project needed when requesting repo list"
      else:
        _data = get_repos()

        print '\nRepos\n'

        if (output == 'json'):
          print _data[ctr]

        elif (output == 'pretty-json'):
										_print_pretty_json(_data)

        else:
          ctr = 0
          while ctr < len(_data):
            if (output == 'list'):
              print _data[ctr]['name']
              ctr +=1
 
    if 'projects' in cmdargs['list']:
      _data = get_projects()

      print '\nProjects\n' 

      if (output == 'json'):
        print _data[ctr]

      elif (output == 'pretty-json'):
        _print_pretty_json(_data)

      else:
        ctr = 0
        while ctr < len(_data):
          if (output == 'list'):
            print _data[ctr]['name']
            ctr +=1

    if 'branches' in cmdargs['list']:
      _data = get_branches()

      print '\nBranches\n' 

      if (output == 'json'):
        print _data[ctr]

      elif (output == 'pretty-json'):
        _print_pretty_json(_data)

      else:
        ctr = 0
        while ctr < len(_data):
          if (output == 'list'):
            print _data[ctr]['displayId']
            ctr +=1

    if 'prs' in cmdargs['list']:
      _data = get_pulls()

      if (output == 'json'):
        print _data[ctr]

      elif (output == 'pretty-json'):
        _print_pretty_json(_data)

      else:
        ctr = 0
        if (_data):
          print '\nPull requests...\n'
          while ctr < len(_data):
            if (output == 'list'):
              if (_data[ctr]['state'] == "OPEN"):
                print _data[ctr]['author']['user']['displayName'], _data[ctr]['title']
                ctr +=1
        else:
          print "No open pull requests found."
  
    sys.exit(0)


  if (cmdargs['commits']):

    ''' IF branches IS NOT PASSED IN, THE THE DEFAULT BRANCH WILL BE QUERIED '''

    _commits = get_commits()

    ctr = 0

    branch_commits = {}

    print "This may take a few seconds..."
    while ctr < len(_commits): 
    
      if (branch):
        sys.stdout.write('.')  
        _branch = get_commit_branch(commit= _commits[ctr]['id']) #time consuming. need better solution

        if _branch.lower() == branch.lower():
          branch_commits[str(_commits[ctr])] = _branch

      else:
        if (output == 'json'):
          print _commits[ctr]
        elif (output == 'pretty-json'):
          _print_pretty_json(_commits[ctr])
        elif (output == 'list'):
          print _commits[ctr]['id'], _commits[ctr]['author']['displayName'], _commits[ctr]['message']

      ctr +=1  

    if (branch):
      print len(branch_commits), "Items\n"

      for k,v in branch_commits.items():
        print k, v

    print('\n') 


  if (cmdargs['hooks']):

    _data = get_hooks()
    print '\nHooks\n'

    if (output == 'json'):
      print _data

    elif (output == 'pretty-json'):
      _print_pretty_json(_data)

    else:
      ctr = 0
      while ctr < len(_data):
        if (output == 'list'):
          print 'Hookname={0}\nconfigured={1}\nenabled={2}\n'.format(_data[ctr]['details']['name'], _data[ctr]['configured'], _data[ctr]['enabled'])
          ctr +=1

  if (cmdargs['sethook']):

    if ((not hookname) or (not hookstatus)):
      raise "hookname and hook action required."

    _hookkey = None

    _data = get_hooks()
    ctr = 0
    while ctr < len(_data):

      if (hookname.lower().strip() == _data[ctr]['details']['name'].lower().strip()):
        _hookkey = _data[ctr]['details']['key']
      ctr +=1

    if not (_hookkey):
      raise "Failed to map hook key"

    print "Performing", hookstatus, "on", hookname, _hookkey

    set_hook(key=_hookkey, status=hookstatus)


  if (cmdargs['createpr']):

    _newrequest = generate_pr( src=from_branch, dest=to_branch, title=cmdargs['title'])

    create_pull_request(data=_newrequest)

 

