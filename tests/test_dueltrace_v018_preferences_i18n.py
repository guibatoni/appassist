"""DUELTRACE v0.18.0 preferences: locale, credits and window persistence."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scanner"))

from dueltrace_preferences import (
    LANGUAGES, DEFAULT_LANGUAGE, public_settings, save_language,
    WindowPreferenceStore, clamp_geometry,
)
from dueltrace_web_security import ProtectedDesktopApi

DEFAULT={"width":1100,"height":760,"min_width":340,"min_height":460}
LANGS={"pt-BR","en","es","ja","zh-CN","it"}


class PreferencesTests(unittest.TestCase):
    def test_every_language_saved_and_original_settings_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            prefs=Path(temp)/"dueltrace_desktop_settings.json"
            prefs.write_text(json.dumps({
                "fusion_tips_visible":False,"epsxe_executable":"C:/Games/epsxe.exe"
            }),encoding="utf8")
            self.assertEqual(set(LANGUAGES),LANGS)
            self.assertEqual(public_settings(prefs)["language"],DEFAULT_LANGUAGE)
            for language in LANGS:
                self.assertEqual(save_language(prefs,language)["language"],language)
                self.assertEqual(public_settings(prefs)["language"],language)
            result=json.loads(prefs.read_text(encoding="utf8"))
            self.assertFalse(result["fusion_tips_visible"])
            self.assertEqual(result["epsxe_executable"],"C:/Games/epsxe.exe")
            for rejected in ("pt","zh","ru",None,123,"../en"):
                with self.assertRaises(ValueError):
                    save_language(prefs,rejected)

    def test_restore_size_position_and_maximized_without_leaking_other_prefs(self):
        with tempfile.TemporaryDirectory() as temp:
            prefs=Path(temp)/"settings.json"
            save_language(prefs,"ja")
            store=WindowPreferenceStore(prefs,1920,1080,DEFAULT)
            store.normal_move(86,103)
            store.normal_resize(1366,810)
            store.flush()
            store.set_maximized(True)
            store.normal_resize(1920,1080) # maximized size must not corrupt normal bounds
            store.close()
            second=WindowPreferenceStore(prefs,1920,1080,DEFAULT)
            start=second.starting_geometry()
            self.assertEqual([start["width"],start["height"]],[1366,810])
            self.assertEqual([start["x"],start["y"]],[86,103])
            self.assertTrue(start["maximized"])
            self.assertEqual(public_settings(prefs)["language"],"ja")
            second.close()

    def test_monitor_changed_or_corrupted_file_recovers_visible_window(self):
        with tempfile.TemporaryDirectory() as temp:
            prefs=Path(temp)/"settings.json"
            prefs.write_text(json.dumps({"window_geometry":{
                "width":4000,"height":3500,"x":-15000,"y":5000,
                "maximized":True}}),encoding="utf8")
            restored=WindowPreferenceStore(prefs,1280,720,DEFAULT).starting_geometry()
            self.assertEqual(restored["width"],1280)
            self.assertEqual(restored["height"],720)
            self.assertEqual(restored["x"],0)
            self.assertEqual(restored["y"],0)
            prefs.write_text("not json",encoding="utf8")
            self.assertEqual(WindowPreferenceStore(
                prefs,1280,720,DEFAULT).starting_geometry()["width"],1100)

    def test_invalid_bounds_do_not_pollute_saved_state(self):
        with tempfile.TemporaryDirectory() as temp:
            prefs=Path(temp)/"settings.json"
            store=WindowPreferenceStore(prefs,1920,1080,DEFAULT)
            for w,h in ((0,300),(100000,100),("1500",800),(True,900)):
                store.normal_resize(w,h)
            store.normal_move("hi",0)
            store.flush()
            self.assertEqual(store.starting_geometry()["width"],1100)
            store.close()

    def test_setting_api_is_token_protected(self):
        bridge=Mock()
        api=ProtectedDesktopApi(bridge,"x"*64)
        with self.assertRaises(PermissionError):
            api.get_ui_settings("wrong")
        with self.assertRaises(PermissionError):
            api.set_ui_language("wrong","it")
        api.get_ui_settings("x"*64)
        api.set_ui_language("x"*64,"it")
        bridge.get_ui_settings.assert_called_once_with()
        bridge.set_ui_language.assert_called_once_with("it")


class TranslationContracts(unittest.TestCase):
    def test_all_six_languages_have_dictionary_values(self):
        files=["i18n-core.ts","i18n-extra.ts","i18n-details.ts"]
        keys=set()
        n=0
        for filename in files:
            raw=(ROOT/"web/lib"/filename).read_text(encoding="utf8")
            rows=json.loads(raw.split(" = ",1)[1])
            for key,values in rows.items():
                self.assertTrue(key.strip())
                self.assertEqual(set(values),LANGS-{"pt-BR"})
                self.assertTrue(all(
                    isinstance(v,str) and len(v.strip())>=1 for v in values.values()))
                keys.add(key)
                n+=1
        self.assertGreaterEqual(len(keys),200)
        self.assertGreaterEqual(n,len(keys))

    def test_settings_visible_and_language_changes_authentic(self):
        shell=(ROOT/"web/components/shell/app-shell.tsx").read_text("utf8")
        sidebar=(ROOT/"web/components/shell/sidebar.tsx").read_text("utf8")
        topbar=(ROOT/"web/components/shell/top-bar.tsx").read_text("utf8")
        settings=(ROOT/"web/components/desktop/settings-page.tsx").read_text("utf8")
        native=(ROOT/"scanner/dueltrace_web_desktop.py").read_text("utf8")
        types=(ROOT/"web/lib/desktop.ts").read_text("utf8")
        self.assertIn("<I18nProvider>",shell)
        self.assertIn('href: "/configuracoes"',sidebar)
        self.assertIn('href="/configuracoes"',topbar)
        self.assertIn("setLocale(next)",settings)
        self.assertIn("Batoni Dev - Guilherme Batoni",settings)
        self.assertIn("Não permitida a distribuição do aplicativo.",settings)
        self.assertIn("window.events.resized+=",native)
        self.assertIn("window.events.moved+=",native)
        self.assertIn("window.events.maximized+=",native)
        self.assertIn("window.events.closing+=",native)
        self.assertIn("WindowPreferenceStore(",native)
        self.assertIn("get_ui_settings(",types)
        self.assertIn("set_ui_language(",types)


if __name__=="__main__":
    unittest.main()
