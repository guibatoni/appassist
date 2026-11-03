"""Integração ePSXe sem shell, sem BIOS/ROM de terceiros e sem abrir processos reais."""
from __future__ import annotations
import tempfile, unittest, sys
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from auto_mods import ModCatalog, atomic_json, supported_for_runtime
from epsxe_launcher import command_for_epsxe, launch_epsxe


class EpsxeTests(unittest.TestCase):
    def setup_files(self, root):
        folder=Path(root);emulator=folder/"Emulador ePSXe"
        emulator.mkdir()
        exe=emulator/"ePSXe.exe";exe.write_bytes(b"simulation only")
        images=folder/"jogos PS1";images.mkdir()
        iso=images/"Yu Gi Oh Remaster 1.2.1 X15.bin"
        iso.write_bytes(b"A"*100_001)
        return exe,iso

    def test_paths_with_spaces_remain_single_subprocess_argument(self):
        with tempfile.TemporaryDirectory() as temp:
            exe,rom=self.setup_files(temp)
            args,cwd=command_for_epsxe(exe,rom)
            self.assertEqual(args[0],str(exe.resolve()))
            self.assertEqual(args[-1],str(rom.resolve()))
            self.assertEqual(args[1:3],["-nogui","-loadiso"])
            self.assertEqual(len(args),4)
            self.assertEqual(cwd,exe.resolve().parent)
            with self.assertRaises(ValueError):
                command_for_epsxe(rom,rom)

    def test_launch_needs_matching_active_profile_and_validates_image(self):
        with tempfile.TemporaryDirectory() as temp:
            exe,rom=self.setup_files(temp)
            cat=ModCatalog(Path(temp)/"data")
            sha="a"*64
            profile={"rom_sha256":sha,"cards":[],"supported_features":{},
                     "verified":{}}
            p=cat.home/"profiles"/sha[:16]/"profile.json"
            atomic_json(p,profile)
            st=rom.stat()
            entry={"sha256":sha,"source_path":str(rom),"profile_path":str(p),
                   "size":st.st_size,"mtime_ns":st.st_mtime_ns,
                   "features":supported_for_runtime(profile)}
            atomic_json(cat.registry_file,{"schema":1,"entries":[entry]})
            proc=Mock()
            with self.assertRaises(PermissionError):
                launch_epsxe(cat,exe,sha,popen=proc,platform="win32")
            self.assertFalse(proc.called)
            atomic_json(cat.active_file,{"sha256":sha,"features":entry["features"]})
            fake=Mock()
            proc.return_value=fake
            self.assertIs(launch_epsxe(cat,exe,sha,popen=proc,platform="win32"),fake)
            args,kw=proc.call_args
            self.assertEqual(args[0][-1],str(rom.resolve()))
            self.assertIs(kw["shell"],False)
            self.assertEqual(Path(kw["cwd"]).resolve(),exe.resolve().parent)
            rom.write_bytes(b"B"*100_005)
            with self.assertRaises(ValueError):
                launch_epsxe(cat,exe,sha,popen=proc,platform="win32")

    def test_non_windows_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            exe,rom=self.setup_files(temp)
            cat=ModCatalog(Path(temp)/"data")
            with self.assertRaises(OSError):
                launch_epsxe(cat,exe,"x"*64,platform="linux",popen=Mock())


if __name__=="__main__":
    unittest.main()
