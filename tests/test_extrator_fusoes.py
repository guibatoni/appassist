"""Testes do formato de fusões (bancos sintéticos, nenhuma ROM real)."""
from __future__ import annotations

import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scanner"))
from extrator_fusoes import (
    BLOCK_SIZE, MIN_INDEX_SIZE, FUSION_BANK_OFFSETS,
    FusionFormatError, decode_bank, analyze_fusion_banks, save_fusion_report,
    select_fusion_resource
)
from auto_mods import ModCatalog, atomic_json, supported_for_runtime


def make_bank(*, change_first=False):
    """40 cartas com 2 fusões cada = 80 receitas válidas no formato WA."""
    data=bytearray(BLOCK_SIZE)
    pos=MIN_INDEX_SIZE
    for a in range(1,41):
        struct.pack_into("<H",data,2+(a-1)*2,pos)
        b1=100+a
        r1=200+a+(1 if change_first and a==1 else 0)
        b2=300+a
        r2=400+a
        # ID <= 255 para b1/r1; demais IDs usam bits altos n3.
        flags=((b1>>8)&3)|(((r1>>8)&3)<<2)|(((b2>>8)&3)<<4)|(((r2>>8)&3)<<6)
        data[pos:pos+6]=bytes([2,flags,b1&255,r1&255,b2&255,r2&255])
        pos+=6
    return bytes(data)


class FakeDisc:
    prefix=None
    def __init__(self,path):
        self.files={"WA_MRG.MRG":(1,len(self.prefix))}
    def get(self,name,limit_bytes=None):
        assert name=="WA_MRG.MRG"
        return self.prefix[:limit_bytes]
    def close(self):
        pass


class FusionBankTests(unittest.TestCase):
    def test_decodes_10_bit_ids_and_mirrored_recipes(self):
        data=decode_bank(make_bank())
        self.assertEqual(data["pointer_count"],40)
        self.assertEqual(data["unique_recipe_count"],80)
        self.assertIn({"a":1,"b":301,"result":401},data["recipes"])
        self.assertIn({"a":1,"b":101,"result":201},data["recipes"])
        self.assertFalse(data["conflicts"])

    def test_rejects_truncated_or_fake_banks(self):
        with self.assertRaises(FusionFormatError):
            decode_bank(b"\0"*100)
        with self.assertRaises(FusionFormatError):
            decode_bank(b"\0"*BLOCK_SIZE)
        damaged=bytearray(make_bank())
        struct.pack_into("<H",damaged,2,1300)
        with self.assertRaises(FusionFormatError):
            decode_bank(bytes(damaged))

    def test_seven_mirrored_banks_and_detect_divergence(self):
        rom_data=bytearray(max(FUSION_BANK_OFFSETS)+BLOCK_SIZE)
        for offset in FUSION_BANK_OFFSETS:
            rom_data[offset:offset+BLOCK_SIZE]=make_bank()
        FakeDisc.prefix=bytes(rom_data)
        with tempfile.TemporaryDirectory() as folder:
            iso=Path(folder)/"fusions.iso"
            iso.write_bytes(b"test image is not really a game")
            with patch("extrator_fusoes.Disc",FakeDisc):
                report=analyze_fusion_banks(iso)
            self.assertEqual(report["valid_banks"],7)
            self.assertEqual(report["matching_banks"],7)
            self.assertEqual(report["candidate_count"],80)
            self.assertFalse(report["verified_in_game"])
            self.assertFalse(report["divergent_banks"])
            rom_data[FUSION_BANK_OFFSETS[-1]:FUSION_BANK_OFFSETS[-1]+BLOCK_SIZE]=make_bank(change_first=True)
            FakeDisc.prefix=bytes(rom_data)
            with patch("extrator_fusoes.Disc",FakeDisc):
                report=analyze_fusion_banks(iso)
            self.assertEqual(report["matching_banks"],6)
            self.assertTrue(report["divergent_banks"])
            self.assertIn("REVISÃO",report["status"])

    def test_renamed_resource_detected_only_with_seven_identical_banks(self):
        raw = bytearray(max(FUSION_BANK_OFFSETS)+BLOCK_SIZE)
        bank = make_bank()
        for offset in FUSION_BANK_OFFSETS:
            raw[offset:offset+BLOCK_SIZE] = bank

        class RenamedDisc:
            files = {"G0SD/GOG_SD1.23": (3, len(raw))}
            def get(self, name, limit_bytes=None):
                return bytes(raw[:limit_bytes])

        name, method = select_fusion_resource(RenamedDisc())
        self.assertEqual(name, "G0SD/GOG_SD1.23")
        self.assertEqual(method, "seven_identical_banks_in_renamed_resource")
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder)/"renamed.iso"
            image.write_bytes(b"example")
            class PatchedDisc(RenamedDisc):
                def __init__(self, path):
                    pass
                def close(self):
                    pass
            with patch("extrator_fusoes.Disc", PatchedDisc):
                result = analyze_fusion_banks(image)
            self.assertEqual(result["matching_banks"],7)
            self.assertEqual(result["valid_banks"],7)
            self.assertEqual(result["candidate_count"],80)
            self.assertFalse(result["verified_in_game"])
            self.assertEqual(result["resource_selection_method"],method)

    def test_renamed_resource_refuses_partial_or_ambiguous_bank_matches(self):
        raw = bytearray(max(FUSION_BANK_OFFSETS)+BLOCK_SIZE)
        for offset in FUSION_BANK_OFFSETS:
            raw[offset:offset+BLOCK_SIZE] = make_bank()

        class ResourceDisc:
            def __init__(self,files,data):
                self.files=files
                self.data=data
            def get(self,name,limit_bytes=None):
                return bytes(self.data[:limit_bytes])

        length=len(raw)
        one=ResourceDisc({"GOG_SD1.23":(1,length)},raw)
        # Six valid copies, one invalid; still not enough to infer format.
        raw[FUSION_BANK_OFFSETS[-1]:FUSION_BANK_OFFSETS[-1]+BLOCK_SIZE]=bytes(BLOCK_SIZE)
        with self.assertRaises(FusionFormatError):
            select_fusion_resource(one)
        raw[FUSION_BANK_OFFSETS[-1]:FUSION_BANK_OFFSETS[-1]+BLOCK_SIZE]=make_bank()
        many=ResourceDisc({"A/ONE.MRG":(1,length),"B/TWO.MRG":(8,length)},raw)
        with self.assertRaises(FusionFormatError):
            select_fusion_resource(many)
        # Canonical name keeps old detection regardless of contents.
        canonical=ResourceDisc({"DATA/WA_MRG.MRG":(1,length)},bytearray(length))
        self.assertEqual(select_fusion_resource(canonical),
                         ("DATA/WA_MRG.MRG","canonical_name"))

    def test_batch_review_requires_explicit_ack_and_seven_consistent_banks(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            catalog=ModCatalog(home)
            sha="a"*64
            iso=home/"fm_original.iso"
            iso.write_bytes(b"test source")
            stat=iso.stat()
            cards=[{"id":i,"name":f"C{i}"} for i in range(1,723)]
            profile={
                "rom_sha256":sha,"cards":cards,
                "verified":{"cartas":"verificado","fusoes":"não_extraídas"},
                "supported_features":{"cards":True,"fusions":False,"ranks":False,"drops":False},
                "fusion_recipes":[],
            }
            path=home/"profiles"/sha[:16]/"profile.json"
            atomic_json(path,profile)
            entry={
                "sha256":sha,"file_name":iso.name,"profile_path":str(path),
                "source_path":str(iso),"size":stat.st_size,"mtime_ns":stat.st_mtime_ns,
                "approved":True,"level":"parcial_revisar",
                "features":supported_for_runtime(profile),"verified":profile["verified"],
            }
            atomic_json(catalog.registry_file,{"schema":1,"entries":[entry]})
            atomic_json(catalog.active_file,{"sha256":sha,"features":entry["features"]})
            decoded=decode_bank(make_bank())
            recipe_rows=decoded["recipes"]
            fp=decoded["recipelist_sha256"]
            banks=[{
                "bank":i,"status":"decodificado","conflict_count":0,
                "unique_recipe_count":len(recipe_rows),"recipelist_sha256":fp,
            } for i in range(1,8)]
            report={
                "rom_sha256":sha,"banks":banks,"valid_banks":7,"matching_banks":7,
                "divergent_banks":False,"bank_conflicts":0,
                "candidate_count":len(recipe_rows),
                "candidate_fingerprint":fp,"candidates":recipe_rows,
            }
            report_path=home/"investigacoes"/(sha+".fusoes.json")
            save_fusion_report(report_path,report)
            with self.assertRaises(PermissionError):
                catalog.review_fusion_batch(sha,expected_fingerprint=fp,acknowledgement="")
            with self.assertRaises(ValueError):
                catalog.review_fusion_batch(sha,expected_fingerprint="0"*64,
                                            acknowledgement="CATALOGO REVISADO")
            # Um banco divergente bloqueia toda a aprovação.
            report["matching_banks"]=6
            save_fusion_report(report_path,report)
            with self.assertRaises(ValueError):
                catalog.review_fusion_batch(sha,expected_fingerprint=fp,
                                            acknowledgement="CATALOGO REVISADO")
            report["matching_banks"]=7
            save_fusion_report(report_path,report)
            # Nunca aprovar se a ISO mudou depois da importação.
            iso.write_bytes(b"tampered")
            with self.assertRaises(ValueError):
                catalog.review_fusion_batch(sha,expected_fingerprint=fp,
                                            acknowledgement="CATALOGO REVISADO")
            iso.write_bytes(b"test source")
            stat=iso.stat()
            entry["mtime_ns"]=stat.st_mtime_ns
            atomic_json(catalog.registry_file,{"schema":1,"entries":[entry]})
            result=catalog.review_fusion_batch(sha,expected_fingerprint=fp,
                                               acknowledgement="CATALOGO REVISADO")
            self.assertEqual(result["count"],80)
            self.assertFalse(result["already_reviewed"])
            approved=catalog.profile_for(entry)
            self.assertEqual(len(approved["fusion_recipes"]),80)
            self.assertTrue(approved["supported_features"]["fusions"])
            self.assertEqual(approved["verified"]["fusoes"],"revisadas_usuario_lote")
            self.assertEqual(approved["fusion_review"]["in_game_individually_verified"],0)
            self.assertTrue((home/"profiles"/sha[:16]/"profile.json.bak.before_fusion_batch").exists())
            self.assertTrue(catalog.current()["features"]["fusoes"])
            repeat=catalog.review_fusion_batch(sha,expected_fingerprint=fp,
                                               acknowledgement="CATALOGO REVISADO")
            self.assertTrue(repeat["already_reviewed"])
            self.assertEqual(repeat["count"],80)
            # A verificação individual posterior pode promover SÓ essa receita.
            first=recipe_rows[0]
            catalog.confirm_fusion(sha,first["a"],first["b"],first["result"])
            approved=catalog.profile_for(entry)
            observed=[r for r in approved["fusion_recipes"]
                      if r["validation"]=="observada_manualmente_no_jogo"]
            self.assertEqual(len(observed),1)
            self.assertEqual(approved["fusion_review"]["in_game_individually_verified"],1)
            # Não libera ranks/score em outros mods.
            self.assertFalse(catalog.current()["features"]["rank"])
            self.assertFalse(catalog.current()["features"]["pontuacao"])

    def test_batch_review_rejects_conflicting_symmetrical_fusion(self):
        with tempfile.TemporaryDirectory() as folder:
            home=Path(folder)
            catalog=ModCatalog(home)
            sha="d"*64
            iso=home/"fm.iso"
            iso.write_bytes(b"mock iso")
            stat=iso.stat()
            profile={
                "rom_sha256":sha,"cards":[{"id":i,"name":str(i)} for i in range(1,723)],
                "verified":{"cartas":"verificado","fusoes":"não_extraídas"},
                "supported_features":{"cards":True,"fusions":False},
                "fusion_recipes":[],
            }
            path=home/"profiles"/sha[:16]/"profile.json"
            atomic_json(path,profile)
            entry={"sha256":sha,"file_name":iso.name,"profile_path":str(path),
                   "source_path":str(iso),"size":stat.st_size,"mtime_ns":stat.st_mtime_ns,
                   "approved":True,"verified":profile["verified"],
                   "features":supported_for_runtime(profile)}
            atomic_json(catalog.registry_file,{"schema":1,"entries":[entry]})
            decoded=decode_bank(make_bank())
            recipes=list(decoded["recipes"])
            recipes.append({"a":recipes[0]["b"],"b":recipes[0]["a"],"result":722})
            # Even if the attacker updated the fingerprint and all 7 bank records
            # to match, overlapping material pairs cannot have two results.
            canonical=sorted(set((r["a"],r["b"],r["result"]) for r in recipes))
            import hashlib
            hash_value=hashlib.sha256(json.dumps(canonical,separators=(",",":")).encode("ascii")).hexdigest()
            banks=[{"bank":i,"status":"decodificado","conflict_count":0,
                    "unique_recipe_count":len(canonical),"recipelist_sha256":hash_value}
                   for i in range(1,8)]
            report={"rom_sha256":sha,"banks":banks,"valid_banks":7,
                    "matching_banks":7,"divergent_banks":False,"bank_conflicts":0,
                    "candidate_count":len(canonical),"candidate_fingerprint":hash_value,
                    "candidates":recipes}
            save_fusion_report(home/"investigacoes"/(sha+".fusoes.json"),report)
            with self.assertRaises(ValueError):
                catalog.review_fusion_batch(sha,expected_fingerprint=hash_value,
                                            acknowledgement="CATALOGO REVISADO")
            self.assertFalse(catalog.profile_for(entry)["supported_features"]["fusions"])

    def test_review_one_pair_only_without_enabling_all(self):
        with tempfile.TemporaryDirectory() as folder:
            catalog=ModCatalog(Path(folder))
            sha="c"*64
            base=Path(folder)
            profile={
                "rom_sha256":sha,"cards":[{"id":i,"name":f"C{i}"} for i in range(1,723)],
                "verified":{"cartas":"verificado","fusoes":"não_extraídas"},
                "supported_features":{"cards":True,"fusions":False,"ranks":False,"drops":False},
                "fusion_recipes":[],
            }
            location=base/"profiles"/sha[:16]/"profile.json"
            atomic_json(location,profile)
            entry={
                "sha256":sha,"file_name":"Teste ISO","profile_path":str(location),
                "source_path":str(base/"test.iso"),"approved":True,
                "level":"parcial_revisar","features":supported_for_runtime(profile),
                "verified":profile["verified"],
            }
            atomic_json(catalog.registry_file,{"schema":1,"entries":[entry]})
            atomic_json(catalog.active_file,{"sha256":sha,"features":entry["features"]})
            report={
                "rom_sha256":sha,"candidate_fingerprint":"f"*64,
                "candidates":[{"a":1,"b":101,"result":201},
                              {"a":1,"b":301,"result":401}],
            }
            save_fusion_report(base/"investigacoes"/(sha+".fusoes.json"),report)
            with self.assertRaises(ValueError):
                catalog.confirm_fusion(sha,1,101,202)
            self.assertFalse(catalog.profile_for(entry)["supported_features"]["fusions"])
            n=catalog.confirm_fusion(sha,1,101,201)
            self.assertEqual(n,1)
            updated=catalog.profile_for(entry)
            self.assertEqual(updated["fusion_recipes"][0]["result"],201)
            self.assertEqual(len(updated["fusion_recipes"]),1)
            self.assertTrue(catalog.current()["features"]["fusoes"])
            self.assertEqual(catalog.confirm_fusion(sha,1,101,201),1)


if __name__=="__main__":
    unittest.main()
