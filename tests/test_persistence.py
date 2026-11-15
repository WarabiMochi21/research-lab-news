import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
import bot

@unittest.skipUnless(shutil.which('git'),'git required')
@unittest.skipIf(os.name == 'nt', 'Windows sandbox blocks Git MSYS local transport; tested by Ubuntu workflow')
class PersistenceTest(unittest.TestCase):
    def test_remote_checkpoint_survives_fresh_checkout(self):
        # Local bare remote; no credentials or network used.
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            remote=root/'remote.git'
            work=root/'state'
            clone=root/'fresh'
            def git(*args,cwd=root):
                subprocess.run(['git',*args],cwd=cwd,check=True,capture_output=True)
            git('init','--bare',str(remote))
            git('init','-b','research-state',str(work))
            git('config','user.name','Fixture',cwd=work)
            git('config','user.email','fixture@example.invalid',cwd=work)
            git('remote','add','origin',str(remote),cwd=work)
            (work/'archive').mkdir()
            bot.atomic_json(work/'archive'/'test.json',{'fixture':True})
            state={'version':1,'items':{'test':{'status':'pending','headline_id':'test'}}}
            bot.checkpoint(work,state,True)
            git('clone','-b','research-state',str(remote),str(clone))
            self.assertEqual(json.loads((clone/'state.json').read_text())['items']['test']['status'],'pending')
