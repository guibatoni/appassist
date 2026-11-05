// DUELTRACE — exportação limitada de referências para comparação com scanner.
// Script opcional de DESENVOLVIMENTO para Ghidra Headless; nunca executado
// pelo DUELTRACE do jogador. Não escreve na ROM nem promove candidatos.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.symbol.Reference;
import ghidra.program.model.symbol.ReferenceIterator;
import java.io.File;
import java.io.PrintWriter;

public class DueltraceXrefs extends GhidraScript {
    private String safe(String raw) {
        return raw == null ? "" : raw.replace("\\", "\\\\")
            .replace("\"", "\\\"").replace("\n", " ").replace("\r", " ");
    }

    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 2 || args.length > 9) {
            throw new IllegalArgumentException(
                "Uso: -postScript DueltraceXrefs.java <saida.json> <endereco1> [enderecos...]");
        }
        File out = new File(args[0]).getCanonicalFile();
        if (out.isDirectory()) {
            throw new IllegalArgumentException("Destino deve ser um arquivo JSON");
        }
        int total = 0;
        try (PrintWriter writer = new PrintWriter(out, "UTF-8")) {
            writer.print("{\"schema\":1,\"status\":\"evidencias_estaticas\",");
            writer.print("\"validated\":false,\"executionConfirmed\":false,");
            writer.print("\"program\":\""+safe(currentProgram.getName())+"\",");
            writer.print("\"targets\":[");
            for (int k=1; k<args.length; k++) {
                if (k>1) writer.print(",");
                Address addr=currentProgram.getAddressFactory().getAddress(args[k]);
                writer.print("{\"address\":\""+safe(args[k])+"\",\"references\":[");
                boolean first=true;
                if (addr!=null) {
                    ReferenceIterator iter=currentProgram.getReferenceManager().getReferencesTo(addr);
                    while (iter.hasNext() && total<64) {
                        if (!first) writer.print(",");
                        Reference ref=iter.next();
                        writer.print("{\"from\":\""+safe(ref.getFromAddress().toString())+"\",");
                        writer.print("\"type\":\""+safe(ref.getReferenceType().toString())+"\"}");
                        first=false;
                        total++;
                    }
                }
                writer.print("]}");
            }
            writer.print("],\"totalReferences\":"+total+"}");
        }
        println("DUELTRACE: arquivo de evidências escrito (somente hipóteses).");
    }
}
