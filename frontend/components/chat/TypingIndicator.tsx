export default function TypingIndicator() {
  return (
    <div className="flex items-start gap-3">
      <div
        className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm"
        style={{ background: "#F0F4FF", border: "1px solid #C7D2FA" }}
      >
        ⚖
      </div>
      <div
        className="rounded-[10px] px-4 py-3 flex items-center gap-1.5"
        style={{
          background: "#FFFFFF",
          border: "1px solid #E5E7EB",
          boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
        }}
      >
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="typing-dot w-[7px] h-[7px] rounded-full"
            style={{ background: "#2D4FD6", animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </div>
    </div>
  );
}
