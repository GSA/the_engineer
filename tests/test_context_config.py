"""Binding errors must not route evidence to another root/project."""
import json
from pathlib import Path
import tempfile
import unittest
from engineer_context.config import load_config, parse_task

TASK = dict(daemon_id='local', project_uid='project-1', issue_uid='task-1', workspace_id='work-1')

def config_value():
    return dict(schema='engineer.context-config/v1',
                librarian=dict(project_id='business-1', executable='bin/librarian-mcp', reader='reader.py', root='corpus', selection='corpus/selected'),
                knowitall=dict(project_id='code-1', repository_id='repo-1', python='bin/python', store='store'))

class ConfigTests(unittest.TestCase):
    def load(self, value, prepare=None):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'binding.json'
        if prepare is not None: prepare(self.path.parent)
        self.path.write_text(json.dumps(value))
        return load_config(self.path)

    def test_config_relative_paths_are_config_relative(self):
        conf = self.load(config_value())
        self.assertEqual(conf.librarian.root, self.path.parent / 'corpus')
        self.assertEqual(conf.knowitall.store, self.path.parent / 'store')
        self.assertEqual(conf.limits.max_bytes, 1048576)

    def test_librarian_reader_is_optional(self):
        # The current toolkit resolves its reader module under its own root, so
        # a binding without a reader must load and stay reader-free.
        value = config_value(); del value['librarian']['reader']
        conf = self.load(value)
        self.assertIsNone(conf.librarian.reader)
        self.assertEqual(self.load(config_value()).librarian.reader, self.path.parent / 'reader.py')

    def test_config_rejects_incomplete_binding_and_bad_limits(self):
        for value in [dict(config_value(), unexpected=True), dict(config_value(), limits={'max_bytes': True}),
                      dict(config_value(), limits={'timeout_seconds': float('inf')}),
                      dict(config_value(), limits={'max_code_queries': -1})]:
            with self.subTest(value=value), self.assertRaises(ValueError): self.load(value)
        for field, bad in [('project_id', ''), ('selection', '../elsewhere'), ('executable', 'exe\nname')]:
            value = config_value(); value['librarian'][field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError): self.load(value)

    def test_binding_paths_may_contain_spaces(self):
        value = config_value()
        value['librarian']['executable'] = 'private tools/librarian-mcp'
        value['knowitall']['python'] = 'private tools/python'
        conf = self.load(value)
        self.assertEqual(conf.librarian.executable, self.path.parent / 'private tools/librarian-mcp')
        self.assertEqual(conf.knowitall.python, self.path.parent / 'private tools/python')

    def test_interpreter_paths_keep_their_selected_symlink(self):
        # A virtual environment's bin/python must be launched through its own
        # path, because resolving the link changes the interpreter's prefix.
        value = config_value()
        def prepare(directory):
            real = directory / 'real-python'; real.write_text('')
            (directory / 'bin').mkdir()
            for name in ('python', 'librarian-mcp'):
                (directory / 'bin' / name).symlink_to(real)
        conf = self.load(value, prepare)
        self.assertEqual(conf.knowitall.python, self.path.parent / 'bin/python')
        self.assertEqual(conf.librarian.executable, self.path.parent / 'bin/librarian-mcp')

    def test_interpreter_paths_collapse_traversal_without_following_links(self):
        value = config_value()
        value['knowitall']['python'] = 'bin/../bin/./python'
        conf = self.load(value)
        self.assertEqual(conf.knowitall.python, self.path.parent / 'bin/python')

    def test_task_requires_exact_nonempty_identity(self):
        self.assertEqual(parse_task(TASK).issue_uid, 'task-1')
        for value in [dict(TASK, issue_uid=''), dict(TASK, project_uid=1), dict(TASK, title='task-1')]:
            with self.assertRaises(ValueError): parse_task(value)
