from sublime import *
from sublime_plugin import TextCommand, EventListener
import os

__version__ = '0.1.0'

def convert(language):
  if language == 'c++': return 'cpp'
  if language == 'cs': return 'csharp'
  return language

class Constants(object):
  @property
  def cache_path(self):
    result = os.path.join(cache_path(), 'Glot')
    if not os.path.exists(result): os.makedirs(result)
    return result
  @property
  def settings(self):
    return load_settings('glot.sublime-settings')
  @property
  def token(self):
    return self.settings.get('token')
  @property
  def languages(self):
    return self.settings.get('languages')
  @property
  def commands(self):
    return self.settings.get('commands')
  @property
  def headers(self):
    ret = {}
    ret['Content-Type'] = 'application/json'
    ret['Authorization'] = 'Token {}'.format(self.token)
    return ret
  @property
  def url_snippets(self):
    return 'https://snippets.glot.io/snippets'
  @property
  def url_snippet(self):
    return 'https://snippets.glot.io/snippets/{}'
  @property
  def url_run(self):
    return 'https://run.glot.io/languages/{}/{}'

C = Constants()
# C.cache_path = %LocalAppData%\Sublime Text 3\Cache\Glot
# C.token      = abcdef.....
# C.languages  = { 'python': ['2', 'latest'] }
# C.commands   = { 'python': 'python main.py' }

class Glot(object):
  @staticmethod
  def make_snippet(language, title, name, content, public=True):
    ret = dict(language=language, title=title, public=public)
    ret['files'] = [dict(name=name, content=content)]
    return ret
  @staticmethod
  def make_payload(language, version, name, content, stdin=None, command=None):
    ret = {}
    ret['files'] = [dict(name=name, content=content)]
    if stdin: ret['stdin'] = stdin
    if command: ret['command'] = command
    url = C.url_run.format(language, version)
    return (url, ret)
  @staticmethod
  def make_request(*args, **kwargs):
    from urllib.request import urlopen, Request
    req = urlopen(Request(*args, headers=C.headers, **kwargs))
    return decode_value(req.read().decode('utf-8'))
  @staticmethod
  def list_snippets():
    return Glot.make_request(C.url_snippets)
  @staticmethod
  def create_snippet(*args, **kwargs):
    data = encode_value(Glot.make_snippet(*args, **kwargs)).encode('utf-8')
    return Glot.make_request(C.url_snippets, data)
  @staticmethod
  def get_snippet(id):
    return Glot.make_request(C.url_snippet.format(id))
  @staticmethod
  def update_snippet(id, *args, **kwargs):
    data = encode_value(Glot.make_snippet(*args, **kwargs)).encode('utf-8')
    return Glot.make_request(C.url_snippet.format(id), data, method='PUT')
  @staticmethod
  def delete_snippet(id):
    return Glot.make_request(C.url_snippet.format(id), method='DELETE')
  @staticmethod
  def run_code(*args, **kwargs):
    url, payload = Glot.make_payload(*args, **kwargs)
    data = encode_value(payload).encode('utf-8')
    return Glot.make_request(url, data)

G = Glot()
# G.list_snippets() = [
#   { modified, owner, title, language, public, files_hash, id, created, url }]
# G.create_snippet(language, title, name, content, public=True)
# G.get_snippet(id) =
#   { modified, owner, title, language, public, files_hash, id, created, url,
#     files: [{ name, content }] }
# G.update_snippet(id, language, title, name, content, public=True)
# G.delete_snippet(id)
# G.run_code(language, version, name, content, stdin=None, command=None)

def async(function):
  def wrapper(*args, **kwargs):
    set_timeout_async(lambda: function(*args, **kwargs))
  return wrapper

def nop(*args):
  pass

class GlotRunCommand(TextCommand):
  def is_enabled(self):
    return C.token is not None
  @async
  def run(self, edit):
    view = self.view
    name = os.path.basename(view.file_name() or 'main.txt')
    region = view.sel()[0]
    if region.empty():
      content = view.substr(Region(0, view.size()))
    else:
      content = view.substr(region)
    language = convert(view.scope_name(0).split()[-1].split('.')[-1])
    if language not in C.languages:
      active_window().status_message('unsupported language')
      return
    versions = C.languages[language]
    @async
    def execute(language, version, name, content):
      active_window().status_message('glot running ...')
      x = G.run_code(language, version, name, content)
      output = x['stdout'] + x['stderr'] + x['error']
      output_panel = active_window().create_output_panel('glot')
      output_panel.run_command('insert_snippet', dict(contents=output))
      active_window().run_command('show_panel', dict(panel='output.glot'))
    if len(versions) > 1:
      @async
      def on_done(index):
        if index == -1: return
        execute(language, versions[index], name, content)
      active_window().show_quick_panel(versions, on_done)
    else:
      execute(language, versions[0], name, content)

class GlotAdvancedRunCommand(TextCommand):
  def is_enabled(self):
    return C.token is not None
  @async
  def run(self, edit):
    view = self.view
    language = convert(view.scope_name(0).split()[-1].split('.')[-1])
    if language not in C.commands:
      active_window().status_message('unsupported language')
      return
    def on_done(stdin):
      command = C.commands[language]
      def on_done(command):
        name = os.path.basename(view.file_name() or 'main.txt')
        region = view.sel()[0]
        if region.empty():
          content = view.substr(Region(0, view.size()))
        else:
          content = view.substr(region)
        versions = C.languages[language]
        @async
        def execute(language, version, name, content):
          active_window().status_message('glot running ...')
          x = G.run_code(language, version, name, content, stdin, command)
          output = x['stdout'] + x['stderr'] + x['error']
          output_panel = active_window().create_output_panel('glot')
          output_panel.run_command('insert_snippet', dict(contents=output))
          active_window().run_command('show_panel', dict(panel='output.glot'))
        if len(versions) > 1:
          @async
          def on_done(index):
            if index == -1: return
            execute(language, versions[index], name, content)
          active_window().show_quick_panel(versions, on_done)
        else:
          execute(language, versions[0], name, content)
      active_window().show_input_panel('Command', command, on_done, nop, nop)
    active_window().show_input_panel('Stdin', '', on_done, nop, nop)

class GlotOpenSnippetCommand(TextCommand):
  def is_enabled(self):
    return C.token is not None
  @async
  def run(self, edit):
    rawlist = G.list_snippets()
    items = [[x['title'], x['language']] for x in rawlist]
    @async
    def on_done(index):
      if index == -1: return
      x = G.get_snippet(rawlist[index]['id'])['files'][0]
      folder = '{}/{}'.format(C.cache_path, rawlist[index]['id'])
      if not os.path.exists(folder): os.makedirs(folder)
      path = '{}/{}'.format(folder, x['name'])
      if not os.path.exists(path):
        with open(path, 'w') as f:
          f.write(x['content'])
      active_window().open_file(path)
    active_window().show_quick_panel(items, on_done)

class GlotNewSnippetCommand(TextCommand):
  def is_enabled(self):
    return C.token is not None
  def run(self, edit):
    view = self.view
    language = convert(view.scope_name(0).split()[-1].split('.')[-1])
    if language not in C.languages:
      active_window().status_message('unsupported language')
      return
    content = view.substr(Region(0, view.size()))
    path = view.file_name()
    if not path:
      active_window().status_message(
        'unsupported temporary file, please save it')
      return
    name = os.path.basename(path)
    @async
    def on_done(title):
      active_window().status_message('sending file ...')
      x = G.create_snippet(language, title, name, content)
      folder = '{}/{}'.format(C.cache_path, x['id'])
      if not os.path.exists(folder): os.makedirs(folder)
      path = '{}/{}'.format(folder, name)
      with open(path, 'w') as f:
        f.write(content)
      active_window().status_message('saved glot snippet {}'.format(title))
    active_window().show_input_panel('Title', 'Untitled', on_done, nop, nop)

class GlotUpdateSnippetCommand(TextCommand):
  def is_enabled(self):
    return C.token is not None
  @async
  def run(self, edit):
    view = self.view
    content = view.substr(Region(0, view.size()))
    language = convert(view.scope_name(0).split()[-1].split('.')[-1])
    if language not in C.languages:
      active_window().status_message('unsupported language')
      return
    path = view.file_name()
    if not path: return
    if not path.startswith(C.cache_path): return
    id, name = os.path.split(path[len(C.cache_path) + 1:])
    if not id: return
    rawlist = G.list_snippets()
    items = dict([(x['id'], x['title']) for x in rawlist])
    if id not in items:
      active_window().status_message('snippet id not exists')
      return
    @async
    def on_done(title):
      G.update_snippet(id, language, title, name, content)
      active_window().status_message('saved glot snippet {}'.format(title))
    active_window().show_input_panel('Title', items[id], on_done, nop, nop)

class GlotDeleteSnippetCommand(TextCommand):
  def is_enabled(self):
    return C.token is not None
  @async
  def run(self, edit):
    rawlist = G.list_snippets()
    items = [[x['title'], x['language']] for x in rawlist]
    @async
    def on_done(index):
      import shutil
      if index == -1: return
      id = rawlist[index]['id']
      title = rawlist[index]['title']
      folder = '{}/{}'.format(C.cache_path, id)
      if os.path.exists(folder):
        try:
          shutil.rmtree(folder)
        except:
          pass
      active_window().status_message('deleting snippet ...')
      G.delete_snippet(id)
      active_window().status_message('deleted snippet {}'.format(title))
    active_window().show_quick_panel(items, on_done)

class GlotSnippetListener(EventListener):
  def on_post_save_async(self, view):
    if C.token is None: return
    view.run_command('glot_update_snippet')
