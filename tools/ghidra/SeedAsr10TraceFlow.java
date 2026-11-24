// Seed instruction/function discovery at trace-verified 68000 addresses in a
// private Ghidra project. Run only against a private copy of the boot ROM.
// The output file and Ghidra project must remain outside the repository.
import java.io.File;
import java.io.PrintWriter;
import java.util.ArrayList;
import java.util.List;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.Listing;

public class SeedAsr10TraceFlow extends ghidra.app.script.GhidraScript {
    // Direct loader/call targets observed in the private firmware trace or
    // independently verified as direct 68000 call destinations.
    private static final String[] FUNCTION_SEEDS = {
        "fff973f0", // generic effect-record loader; called from ROM wrappers
        "fff97744", // traced HALT/DRAM-clear preamble
        "fff97776", // common host-port transfer helper
        "fff97662", // common post-RUN/register exchange helper call target
        "fff977c6"  // traced RUN release helper
    };
    private static final String[] TRACE_PCS = {
        "fff977b0", "fff977b8", "fff97752", "fff9775c",
        "fff97678", "fff97680", "fff97776", "fff97792",
        "fff97796", "fff977c6", "fff977d2", "fff973ba"
    };

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            printerr("usage: SeedAsr10TraceFlow.java <private-output.txt>");
            return;
        }
        File output = new File(args[0]);
        File parent = output.getParentFile();
        if (parent != null && !parent.isDirectory()) parent.mkdirs();

        Listing listing = currentProgram.getListing();
        List<Address> roots = new ArrayList<>();
        try (PrintWriter w = new PrintWriter(output, "UTF-8")) {
            w.println("program=" + currentProgram.getName());
            w.println("language=" + currentProgram.getLanguage().getLanguageID().getIdAsString());
            w.println("default_space=" + currentProgram.getAddressFactory().getDefaultAddressSpace());
            w.println("program_min=" + currentProgram.getMinAddress() + ",program_max=" + currentProgram.getMaxAddress());
            for (ghidra.program.model.mem.MemoryBlock block : currentProgram.getMemory().getBlocks()) {
                w.println("block=" + block.getName() + ",start=" + block.getStart() + ",end=" + block.getEnd() +
                          ",read=" + block.isRead() + ",write=" + block.isWrite() + ",execute=" + block.isExecute() +
                          ",initialized=" + block.isInitialized());
            }
            for (String text : FUNCTION_SEEDS) {
                Address a = toAddr(Long.parseLong(text, 16));
                roots.add(a);
                Instruction i = listing.getInstructionAt(a);
                if (i == null) {
                    // Trace/call evidence takes precedence over auto-analysis
                    // data typing at these exact private firmware addresses.
                    clearListing(a, a.add(1));
                    disassemble(a);
                    i = listing.getInstructionAt(a);
                }
                if (i != null && currentProgram.getFunctionManager().getFunctionAt(a) == null) {
                    createFunction(a, null);
                }
                w.println("seed=" + a + ",instruction=" + (i == null ? "unavailable" : i.toString()) +
                          ",function=" + currentProgram.getFunctionManager().getFunctionAt(a));
            }
            for (String text : TRACE_PCS) {
                Address a = toAddr(Long.parseLong(text, 16));
                Instruction i = listing.getInstructionAt(a);
                if (i == null) {
                    clearListing(a, a.add(1));
                    disassemble(a);
                    i = listing.getInstructionAt(a);
                }
                w.println("trace_pc=" + a + ",instruction=" + (i == null ? "unavailable" : i.toString()) +
                          ",containing_function=" + currentProgram.getFunctionManager().getFunctionContaining(a));
            }

            DecompInterface decompiler = new DecompInterface();
            decompiler.openProgram(currentProgram);
            try {
                for (Address a : roots) {
                    Function f = currentProgram.getFunctionManager().getFunctionAt(a);
                    if (f == null) continue;
                    DecompileResults result = decompiler.decompileFunction(f, 30, monitor);
                    w.println("\n--- decompile " + a + " ---");
                    w.println(result.getDecompiledFunction() == null ?
                              "unavailable: " + result.getErrorMessage() :
                              result.getDecompiledFunction().getC());
                }
            } finally {
                decompiler.dispose();
            }
        }
        println("Wrote private trace-seeded analysis to " + output.getAbsolutePath());
    }
}
