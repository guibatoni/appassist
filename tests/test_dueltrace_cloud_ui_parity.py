"""Cloud UI parity and local connection regressions.

A shared visual shell must not become a different product when rendered in
Chrome. The native Windows tools remain restricted to pywebview.
"""
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/"web"
def source(path):
    return (UI/path).read_text(encoding="utf-8")


class CloudUIParityTests(unittest.TestCase):
    def test_cloud_reuses_original_shell_branding_background_and_navigation(self):
        shell=source("components/shell/app-shell.tsx")
        self.assertIn('src="/bg-temple.png"',shell)
        self.assertIn("<TopBar />",shell)
        self.assertIn("<Sidebar />",shell)
        self.assertIn("<CloudUiProvider>",shell)
        self.assertNotIn('if(route.startsWith("/cloud")){\n    return <>{children}</>',shell)

    def test_cloud_uses_original_logo_without_native_window_controls(self):
        top=source("components/shell/top-bar.tsx")
        self.assertIn("<Logo />",top)
        self.assertIn("isCloud",top)
        self.assertIn('{!isCloud&&<div',top)
        self.assertIn("<WindowControls />",top)
        self.assertIn("Conector desconectado",top)
        self.assertIn('setTab("configuracoes")',top)

    def test_original_eight_sidebar_categories_on_cloud(self):
        sidebar=source("components/shell/sidebar.tsx")
        context=source("lib/cloud-ui.tsx")
        self.assertIn('pathname.startsWith("/cloud")',sidebar)
        self.assertIn("setTab(cloudTab)",sidebar)
        self.assertIn("CLOUD_NAV[index]",sidebar)
        self.assertEqual(context.count('label:"'),8)
        for key in ("inicio","mods","biblioteca","fusoes","drops","oponentes",
                    "decks","configuracoes"):
            self.assertIn('id:"'+key+'"',context)

    def test_connector_submit_is_never_hydration_disabled_and_reports_clicks(self):
        page=source("components/cloud/cloud-prototype.tsx")
        self.assertIn('data-cloud-build="0.2.2"',page)
        self.assertIn('Cliques reconhecidos: {connectAttempts}',page)
        self.assertIn('const [connectAttempts,setConnectAttempts]=useState(0)',page)
        self.assertIn('setConnectAttempts(n=>n+1)',page)
        self.assertIn('onSubmit={event=>{event.preventDefault();if(!busy)void connect()}}',page)
        self.assertIn('type="submit" disabled={busy}',page)
        self.assertNotIn('disabled={busy||!clientReady}',page)
        self.assertIn('Interface {clientReady?"iniciada":"aguardando inicialização do JavaScript"}',page)
        self.assertIn('Clique recebido. Consultando o Connector',page)
        self.assertIn('role="alert"',page)

    def test_chrome_password_autofill_uses_real_dom_value_on_connect(self):
        page=source("components/cloud/cloud-prototype.tsx")
        self.assertIn("const pairingInputRef=useRef<HTMLInputElement>(null)",page)
        self.assertIn('const key=pairingInputRef.current?.value.trim()??""',page)
        self.assertIn('onInput={syncPairingField}',page)
        self.assertIn('onFocus={syncPairingField}',page)
        self.assertIn('onBlur={syncPairingField}',page)
        self.assertIn('ref={pairingInputRef} defaultValue=""',page)
        self.assertNotIn('value={pairKey}',page)
        self.assertIn('setPairKeyLength(key.length)',page)
        self.assertIn('if(pairingInputRef.current)pairingInputRef.current.value=""',page)
        self.assertIn('autoComplete="new-password"',page)

    def test_local_http_timeout_and_actionable_error_message(self):
        api=source("lib/cloud-local.ts")
        self.assertIn("new AbortController()",api)
        self.assertIn("controller.abort()",api)
        self.assertIn("window.clearTimeout(timeout)",api)
        self.assertIn("127.0.0.1:8765",api)
        self.assertIn('credentials:"omit"',api)

    def test_cloud_pages_use_original_card_panels_and_actual_art_from_pc(self):
        page=source("components/cloud/cloud-prototype.tsx")
        self.assertIn('const panel="panel rounded-xl',page)
        self.assertIn('const head="panel rounded-xl border-gold/40',page)
        self.assertIn("ImageFromPC",page)
        self.assertIn("cloudArt(token,sha,card.id)",page)
        self.assertIn('tab==="fusoes"',page)
        self.assertIn('tab==="biblioteca"',page)
        self.assertIn("Cartas por página",page)
        self.assertIn("role=\"dialog\"",page)
        self.assertIn("tab===\"configuracoes\"",page)

    def test_no_upload_or_browser_storage_for_private_game_data(self):
        api=source("lib/cloud-local.ts")
        page=source("components/cloud/cloud-prototype.tsx")
        self.assertNotIn("localStorage",api+page)
        self.assertNotIn("sessionStorage",api+page)
        self.assertNotIn("FormData",api+page)
        self.assertNotIn("new FileReader",api+page)
        self.assertIn('"/v1/import"',page)
        self.assertIn("{chooseLocalFile:true}",page)


if __name__=="__main__":
    unittest.main()
