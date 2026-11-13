"use strict";
/* Synthetic fixture only: generated in memory, not a copyrighted PS1 ISO. */
const test=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");
const {webcrypto}=require("node:crypto");
const {File}=require("node:buffer");
const {TextDecoder}=require("node:util");
const code=fs.readFileSync(require("node:path").resolve(__dirname,"../public/cloud-online/iso-scanner.js"),"utf8");
const context={window:{},File,TextDecoder,crypto:webcrypto,Uint8Array,Uint16Array,Array,Set,Map,console};
vm.runInNewContext(code,context);
const scanner=context.window.DueltraceIsoScanner;

const PTR=0x1c6000,TEXT=0x1c0800,GLYPH=0x1c9800,ATTR=0x1c4a44,DETAIL=0x1c5b33;
const exesize=0x1ca000;
function executable(){
  const exe=Buffer.alloc(exesize);
  exe.write("PS-X EXE",0,"ascii");
  const glyphs=[0,0x8260,0x824F,0x8250,0x8251,0x8252,0x8253,
    0x8254,0x8255,0x8256,0x8257,0x8258];
  glyphs.forEach((v,i)=>exe.writeUInt16LE(v,GLYPH+i*4));
  let pointer=50;
  function add(index,n){
    const chars=String(n).padStart(4,"0");
    const bytes=[0xf8,0x0a,0x00,1,...[...chars].map(d=>Number(d)+2),0xff];
    exe.writeUInt16LE(pointer,PTR+index*2);
    Buffer.from(bytes).copy(exe,TEXT+pointer);
    pointer+=bytes.length;
  }
  for(let i=1;i<=722;i++){
    add(i,i);
    const packed=(1<<26)|300|(250<<9);
    exe.writeUInt32LE(packed>>>0,ATTR+(i-1)*4);
    exe[DETAIL+i-1]=4;
  }
  for(let i=1;i<=39;i++)add(0x328+i,i);
  return exe;
}
function rec(name,lba,bytes,folder=false){
  const len=33+name.length+(name.length%2===0?1:0);
  const row=Buffer.alloc(len);row[0]=len;row.writeUInt32LE(lba,2);
  row.writeUInt32LE(bytes,10);row[25]=folder?2:0;row[32]=name.length;
  row.write(name,33,"ascii");return row;
}
function fileFromISO(raw=false){
  const exe=executable();
  const sector=2048,exeLba=24;
  const sectors=Math.ceil(exe.length/sector),n=exeLba+sectors+2;
  const iso=Buffer.alloc(n*sector);
  iso[16*sector]=1;
  iso.write("CD001",16*sector+1,"ascii");
  iso[16*sector+6]=1;
  const root=rec("\0",20,2048,true);
  root.copy(iso,16*sector+156);
  rec("SLUS_000.00;1",exeLba,exe.length).copy(iso,20*sector);
  exe.copy(iso,exeLba*sector);
  if(!raw)return new File([iso],"fixture.iso");
  const bin=Buffer.alloc(n*2352);
  for(let i=0;i<n;i++)iso.copy(bin,i*2352+24,i*2048,i*2048+2048);
  return new File([bin],"fixture.bin");
}
test("scanner works directly on ISO9660 browser File, no connector",async()=>{
  const catalog=await scanner.scan(fileFromISO());
  assert.equal(catalog.cards.length,722);
  assert.equal(catalog.opponents.length,39);
  assert.equal(catalog.cards[0].name,"A0001");
  assert.equal(catalog.cards[0].atk,3000);
  assert.equal(catalog.cards[0].def,2500);
  assert.equal(catalog.cards[0].type,"Mago");
  assert.equal(catalog.opponents[38].name,"A0039");
  assert.equal(catalog.fusions.length,0);
  assert.equal(catalog.drops.length,0);
  assert.equal(catalog.confidence,"estrutural_nao_verificado_no_jogo");
  assert.match(catalog.id,/^[a-f0-9]{64}$/);
});
test("scanner recognizes BIN RAW 2352 Mode 2 from content",async()=>{
  const catalog=await scanner.scan(fileFromISO(true));
  assert.equal(catalog.cards.length,722);
  assert.equal(catalog.geometry,"BIN RAW 2352 Mode 2");
});
test("unknown format is rejected instead of inventing card data",async()=>{
  const file=new File([Buffer.alloc(90000)],"bad.iso");
  await assert.rejects(scanner.scan(file),/ISO9660 reconhecido/);
});
test("ISO file extension and size are validated",async()=>{
  await assert.rejects(scanner.scan(new File([Buffer.alloc(100000)],"bad.exe")),/Formato aceito/);
  await assert.rejects(scanner.scan(new File([Buffer.alloc(1000)],"bad.iso")),/Tamanho/);
});
test("hosted portal never requires or loads a connector",()=>{
  const html=fs.readFileSync(require("node:path").resolve(__dirname,"../public/cloud-online/index.html"),"utf8");
  const js=fs.readFileSync(require("node:path").resolve(__dirname,"../public/cloud-online/app.js"),"utf8");
  assert.ok(html.includes('src="./iso-scanner.js"'));
  assert.ok(html.includes('src="./catalog-store.js"'));
  assert.ok(html.includes("Importar ISO/BIN"));
  assert.ok(!html.includes("localhost"));
  assert.ok(!js.includes('http://127.0.0.1'));
  assert.ok(!js.includes("Authorization:"));
  assert.ok(!js.includes("fetch("));
});
