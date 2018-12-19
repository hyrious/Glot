from urllib.request import *
import os, sublime, sublime_plugin

def setting(name):
  return sublime.load_settings("glot.sublime-settings").get(name)

def token():
  return setting("token")

def languages():
  return setting("languages") or {}

def versions(l):
  return languages()[l] or []

def command(l):
  return setting("commands")[l]

def headers():
  return {  'Content-type': 'application/json',
           'Authorization': 'Token {}'.format(token()) }

def content(v):
  return v.substr(v.sel()[0]) or v.substr(sublime.Region(0, v.size()))

def language(v):
  return v.scope_name(v.sel()[0].a).split()[0].split('.')[-1]

def request(*a, **kw):
  return urlopen(Request(*a, headers=headers(), **kw)).read().decode('utf-8')

def get(url):
  return sublime.decode_value(request(url))

def post(url, data):
  ret = request(url, sublime.encode_value(data).encode('utf-8'))
  return sublime.decode_value(ret)

def put(url, data):
  ret = request(url, sublime.encode_value(data).encode('utf-8'), method='PUT')
  return sublime.decode_value(ret)

def delete(url):
  return sublime.decode_value(request(url, method='DELETE'))

# https://github.com/prasmussen/glot-snippets/tree/master/api_docs
def make_snippet(language, title, name, content):
  return { "language": language,
           "title"   : title,
           "public"  : False,
           "files"   : [{ "name": name, "content": content }] }

def list_snippets():
  return get('https://snippets.glot.io/snippets')

def create_snippet(language, title, name, content):
  return post('https://snippets.glot.io/snippets',
              make_snippet(language, title, name, content))

def get_snippet(id):
  return get('https://snippets.glot.io/snippets/{}'.format(id))

def update_snippet(id, language, title, name, content):
  return put('https://snippets.glot.io/snippets/{}'.format(id),
             make_snippet(language, title, name, content))

def delete_snippet(id):
  return delete('https://snippets.glot.io/snippets/{}'.format(id))

# https://github.com/prasmussen/glot-run/tree/master/api_docs
def run_code(language, version, name, content, stdin=None, command=None):
  payload = { 'files': [{ 'name': name, 'content': content }] }
  if stdin: payload['stdin'] = stdin
  if command: payload['command'] = command
  url = 'https://run.glot.io/languages/{}/{}'.format(language, version)
  return post(url, payload)

class GlotOpenSnippetCommand(sublime_plugin.TextCommand):
  def is_visible(self):
    return token() is not None
  def run(self, edit):
    sublime.set_timeout_async(self.task, 0)
  def task(self):
    self.win = sublime.active_window()
    self.win.status_message('loading snippets...')
    self.data = list_snippets()
    items = [x['title'] for x in self.data]
    self.win.show_quick_panel(items, self.task1, 1)
  def task1(self, index):
    self.id = self.data[index]['id']
    self.lang = self.data[index]['language']
    self.win.status_message('loading {}...'.format(self.id))
    sublime.set_timeout_async(self.task2, 0)
  def task2(self):
    syntax = 'Packages/{0}/{0}.tmLanguage'.format(self.lang.capitalize())
    for file in get_snippet(self.id)['files']:
      view = self.win.new_file()
      view.set_syntax_file(syntax)
      view.run_command('insert_snippet', { 'contents': file['content'] })

class GlotRunCommand(sublime_plugin.TextCommand):
  def is_visible(self):
    return token() is not None
  def run(self, edit):
    sublime.set_timeout_async(self.task, 0)
  def task(self):
    self.win = sublime.active_window()
    self.versions = versions(language(self.view))
    l, c = language(self.view), content(self.view)
    n = os.path.basename(self.view.file_name())
    self.payload = [l, self.versions[0], n, c]
    if not self.versions:
      sublime.message_dialog('not support such language')
      return
    if len(self.versions) > 1:
      sublime.set_timeout_async(self.task_select_version, 0)
      return
    sublime.set_timeout_async(self.task_action, 0)
  def task_select_version(self):
    self.win.show_quick_panel(self.versions, self.on_done, 1)
  def on_done(self, index):
    self.payload[1] = self.versions[index]
    sublime.set_timeout_async(self.task_action, 0)
  def task_action(self):
    self.win.status_message('sending request...')
    ret = run_code(*self.payload)
    view = self.win.create_output_panel("glot_output")
    self.win.run_command("show_panel", { "panel": "output.glot_output" })
    content = ret['stdout'] + ret['stderr'] + ret['error']
    view.run_command('insert', { 'characters': content })
