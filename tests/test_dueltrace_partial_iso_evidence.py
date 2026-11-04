"""Separação entre matrizes WA estruturalmente coerentes e drops utilizáveis.

Mod GOG pode produzir 117 tabelas / milhares de registros, mas não ter
cartas ou oponentes reconhecidos. Não publicar entradas com IDs sem nomes
confiáveis, preservando as evidências por SHA.
"""
from __future__ import annotations
import csv
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from importador_perfis import analyse, rows
from scanner_multiiso import X15_SHA


class PartialWAEvidenceTests(unittest.TestCase):
    def setUp(self):
        self._tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root=Path(self._tmp.name)
        self.source=self.root/"GOG MOD 2.2.iso"
        self.source.write_bytes(b"invalid synthetic ISO")
        self.info={
            "sha256":"6"*64,
            "executavel":"GOG_VNT.223",
            "drops_source":"GOSD/GOG_SD1.23",
            "hash_wa":"a"*64,
            "hash_executavel":"b"*64,
            "wa_prefix_bytes":38148608,
        }

    def csv(self,name,rows):
        with (self.root/name).open("w",encoding="utf-8",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    def write_wa(self,entries=5,*,complete=False):
        if complete:
            self.csv("drops_por_oponente.csv",[
                {"oponente_id":oid,"rank":group,"carta_id":index+1,
                 "peso":2048,"chance_percentual":100.0,"source_offset":1024+index*2}
                for oid in range(1,40)
                for index,group in enumerate(("S-POW","S-TEC","A-POW"))])
        else:
            self.csv("drops_por_oponente.csv",[
                {"oponente_id":i%39+1,"rank":"S-POW",
                 "carta_id":i%722+1,"peso":1,"chance_percentual":0.048828125,
                 "source_offset":1024+i*2} for i in range(entries)])
        self.csv("validacao_pesos.csv",[
            {"oponente_id":i//3+1,
             "rank":["S-POW","S-TEC","A-POW"][i%3],
             "peso_total":2048,"codificacao":"simples",
             "source_offset":i*0x5b4} for i in range(117)])
        self.csv("decks.csv",[
            {"oponente_id":1,"carta_id":1,"peso":2}])

    def write_identity_catalogs(self):
        self.csv("oponentes.csv",[
            {"id":i,"nome":f"Oponente {i}"} for i in range(1,40)])
        self.csv("cartas.csv",[
            {"id":i,"nome":f"Carta {i}","atk":1000,"def":800,
             "tipo":3,"nivel":4,"atributo":1,"estrela_1":2,"estrela_2":5}
            for i in range(1,723)])

    def test_gog_wa_evidence_without_names_not_assigned(self):
        self.write_wa()
        profile=analyse(self.root,self.info,self.source)
        self.assertFalse(profile["supported_features"]["cards"])
        self.assertFalse(profile["supported_features"]["opponents"])
        self.assertFalse(profile["supported_features"]["drops"])
        self.assertFalse(profile["supported_features"]["ranks"])
        self.assertEqual(profile["drops"],[])
        self.assertEqual(profile["verified"]["tabelas_drops"],
                         "matrizes_candidatas_sem_identidade")
        provenance=profile["drops_provenance"]
        self.assertEqual(provenance["source"],"GOSD/GOG_SD1.23")
        self.assertEqual(provenance["candidate_table_count"],117)
        self.assertEqual(provenance["candidate_entry_count"],5)
        self.assertEqual(provenance["table_count"],0)
        self.assertEqual(provenance["candidate_weight_total"],2048)
        self.assertFalse(provenance["in_game_verified"])
        self.assertFalse(provenance["rank_label_verified"])

    def test_full_card_and_opponent_catalog_restores_confirmed_groups(self):
        self.write_wa(complete=True)
        self.write_identity_catalogs()
        profile=analyse(self.root,self.info,self.source)
        self.assertTrue(profile["supported_features"]["cards"])
        self.assertTrue(profile["supported_features"]["opponents"])
        self.assertTrue(profile["supported_features"]["drops"])
        self.assertEqual(profile["verified"]["tabelas_drops"],"verificado")
        self.assertEqual(len(profile["drops"]),117)
        self.assertEqual(profile["drops_provenance"]["table_count"],117)
        self.assertEqual(profile["drops_provenance"]["candidate_table_count"],117)
        self.assertFalse(profile["drops_provenance"]["rank_label_verified"])

    def test_x15_known_hash_retains_exclusive_rank_system(self):
        self.write_wa(complete=True)
        self.write_identity_catalogs()
        self.info["sha256"]=X15_SHA
        profile=analyse(self.root,self.info,self.source)
        self.assertEqual(profile["rank_system"],"x15")
        self.assertEqual(profile["rank_labels"],["Z-POW","S-POW","S-TEC"])
        self.assertEqual(profile["verified"]["tabelas_drops"],"verificado")
        self.assertTrue(profile["drops_provenance"]["rank_label_verified"])

    def test_corrupted_weights_not_presented_even_as_candidates(self):
        self.write_wa()
        p=self.root/"validacao_pesos.csv"
        text=p.read_text(encoding="utf8").replace("2048","1024")
        p.write_text(text,encoding="utf8")
        profile=analyse(self.root,self.info,self.source)
        self.assertFalse(profile["supported_features"]["drops"])
        self.assertEqual(profile["drops_provenance"]["candidate_table_count"],0)
        self.assertEqual(profile["drops_provenance"]["candidate_entry_count"],0)

    def test_catalogue_does_not_promote_inconsistent_provisional_rows(self):
        self.write_wa()
        self.write_identity_catalogs()
        profile=analyse(self.root,self.info,self.source)
        self.assertTrue(profile["supported_features"]["cards"])
        self.assertFalse(profile["supported_features"]["drops"])
        self.assertEqual(profile["verified"]["tabelas_drops"],"matrizes_candidatas_inconsistentes")
        provenance=profile["drops_provenance"]
        self.assertEqual(provenance["candidate_entry_count"],5)
        self.assertEqual(provenance["rom_sha256"],self.info["sha256"])
        self.assertIn("drop_weights_do_not_match_matrices",
                      provenance["association_validation"]["errors"])
        self.assertEqual(len(rows(self.root/"drops_por_oponente.csv")),5)

    def test_probability_is_computed_from_weight_not_imported_csv_text(self):
        self.write_wa(complete=True)
        self.write_identity_catalogs()
        path=self.root/"drops_por_oponente.csv"
        records=rows(path)
        records[0]["chance_percentual"]="NaN / untrusted report value"
        self.csv(path.name,records)
        profile=analyse(self.root,self.info,self.source)
        self.assertTrue(profile["supported_features"]["drops"])
        self.assertEqual(profile["drops"][0]["probability_percent"],100.0)

    def test_out_of_range_card_id_and_attributes_stay_quarantined(self):
        self.write_wa(complete=True)
        self.write_identity_catalogs()
        records=rows(self.root/"drops_por_oponente.csv")
        records[-1]["carta_id"]="723"
        self.csv("drops_por_oponente.csv",records)
        self.assertFalse(analyse(self.root,self.info,self.source)["supported_features"]["drops"])
        records=rows(self.root/"cartas.csv")
        records[-1]["atk"]="-100"
        self.csv("cartas.csv",records)
        profile=analyse(self.root,self.info,self.source)
        self.assertFalse(profile["supported_features"]["cards"])
        self.assertTrue(profile["supported_features"]["opponents"])
        self.assertFalse(profile["supported_features"]["drops"])


if __name__=="__main__":
    unittest.main()
