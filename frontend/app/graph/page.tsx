import PageHeader from "@/components/layout/PageHeader";

export default function GraphPage() {
  return (
    <div className="flex flex-col h-full">
      <PageHeader
        title="Knowledge Graph"
        subtitle="Neo4j · JP/US statute and case law graph"
      />

      <div className="flex-1 flex flex-col items-center justify-center bg-[#F5F6F8] px-8 text-center">
        <div className="text-5xl mb-5">🕸</div>
        <h2
          className="text-[20px] text-[#111827] mb-3"
          style={{ fontFamily: "var(--font-dm-serif)" }}
        >
          Knowledge Graph
        </h2>
        <p className="text-[14px] text-[#6B7280] max-w-md leading-relaxed mb-6">
          Interactive visualization of the legal knowledge graph. Explore relationships between
          statutes, cases, provisions, entities, and legal concepts across JP and US jurisdictions.
        </p>

        {/* Neo4j connection badge */}
        <div
          className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg text-[12px]"
          style={{ background: "#FFFFFF", border: "1px solid #E5E7EB" }}
        >
          <span className="text-[#9CA3AF]">Neo4j AuraDB</span>
          <span
            className="text-[11px] px-2 py-0.5 rounded"
            style={{
              fontFamily: "var(--font-ibm-plex-mono)",
              background: "#EEF2FF",
              color: "#4F46E5",
              border: "1px solid #C7D2FA",
            }}
          >
            bolt://localhost:7687
          </span>
        </div>

        <div
          className="mt-8 grid grid-cols-3 gap-4 max-w-lg text-center"
        >
          {[
            { label: "Node Types", value: "7", detail: "Statute · Case · Provision · Concept · Entity · Regulation · Chunk" },
            { label: "Relationships", value: "9", detail: "CITES · INTERPRETS · AMENDS · IMPLEMENTS · OVERRULES · ANALOGOUS_TO…" },
            { label: "Jurisdictions", value: "2", detail: "JP (会社法 · 金商法) · US (Delaware · SEC)" },
          ].map(({ label, value, detail }) => (
            <div
              key={label}
              className="rounded-lg p-4"
              style={{ background: "#FFFFFF", border: "1px solid #E5E7EB" }}
            >
              <div
                className="text-[24px] font-bold text-[#2D4FD6] mb-1"
                style={{ fontFamily: "var(--font-dm-serif)" }}
              >
                {value}
              </div>
              <div className="text-[12px] font-semibold text-[#374151] mb-1">{label}</div>
              <div className="text-[10px] text-[#9CA3AF] leading-snug">{detail}</div>
            </div>
          ))}
        </div>

        <p className="mt-8 text-[12px] text-[#9CA3AF]">
          Neo4j Bloom integration or D3.js force graph coming soon. Connect your AuraDB instance.
        </p>
      </div>
    </div>
  );
}
